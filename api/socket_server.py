import socketio
import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# Create Async Socket.IO Server with ASGI support
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)


@sync_to_async
def _save_message_to_db(company_id, sender_name, sender_role, message, is_admin):
    from api.models import SupportMessage, Company
    company = None
    if company_id:
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            pass

    msg = SupportMessage.objects.create(
        company=company,
        sender_name=sender_name or ('Super Admin' if is_admin else 'Company User'),
        sender_role=sender_role or ('super_admin' if is_admin else 'company_admin'),
        message=message,
        is_admin=is_admin,
        is_read=False,
    )
    return {
        'id': msg.id,
        'company': company.id if company else None,
        'company_id': company.id if company else None,
        'company_name': company.name if company else 'Global',
        'sender_name': msg.sender_name,
        'sender_role': msg.sender_role,
        'message': msg.message,
        'attachment': None,
        'attachment_url': None,
        'is_admin': msg.is_admin,
        'is_read': msg.is_read,
        'created_at': msg.created_at.isoformat(),
        'updated_at': msg.updated_at.isoformat() if hasattr(msg, 'updated_at') and msg.updated_at else msg.created_at.isoformat(),
    }


@sio.event
async def connect(sid, environ, auth=None):
    logger.info(f"[Socket.IO] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    logger.info(f"[Socket.IO] Client disconnected: {sid}")


@sio.event
async def join_company(sid, data):
    """
    Company client joins their dedicated room: company_{company_id}
    """
    company_id = data.get('company_id') if isinstance(data, dict) else data
    if company_id:
        room = f"company_{company_id}"
        await sio.enter_room(sid, room)
        logger.info(f"[Socket.IO] sid {sid} joined room {room}")
        await sio.emit('joined_room', {'room': room, 'status': 'connected'}, to=sid)


@sio.event
async def join_admin(sid, data=None):
    """
    Super Admin joins the global admin support monitoring room
    """
    await sio.enter_room(sid, "admin_support")
    logger.info(f"[Socket.IO] Admin sid {sid} joined admin_support room")
    await sio.emit('joined_room', {'room': 'admin_support', 'status': 'connected'}, to=sid)


@sio.event
async def join_admin_hub(sid, data=None):
    """
    Alias for join_admin
    """
    await sio.enter_room(sid, "admin_support")
    logger.info(f"[Socket.IO] Admin sid {sid} joined admin_support room via join_admin_hub")
    await sio.emit('joined_room', {'room': 'admin_support', 'status': 'connected'}, to=sid)


@sio.event
async def send_message(sid, data):
    """
    Handles inbound messages from either company user or admin.
    Broadcasts in real-time to both the company room and the admin support room.
    """
    company_id = data.get('company_id') or data.get('company')
    message = data.get('message', '').strip()
    sender_name = data.get('sender_name', 'User')
    sender_role = data.get('sender_role', 'company_admin')
    is_admin = bool(data.get('is_admin', False))

    if not message:
        return {'status': 'error', 'message': 'Message cannot be empty'}

    # Save to persistent database
    saved_msg = await _save_message_to_db(
        company_id=company_id,
        sender_name=sender_name,
        sender_role=sender_role,
        message=message,
        is_admin=is_admin
    )

    # 1. Broadcast to company room
    if company_id:
        await sio.emit('new_message', saved_msg, room=f"company_{company_id}")

    # 2. Broadcast to admin support desk room
    await sio.emit('new_message', saved_msg, room="admin_support")

    return {'status': 'success', 'data': saved_msg}


@sio.event
async def typing(sid, data):
    """
    Real-time typing indicator
    """
    company_id = data.get('company_id')
    is_admin = data.get('is_admin', False)
    name = data.get('name', 'Someone')

    payload = {'name': name, 'is_admin': is_admin, 'company_id': company_id}

    if is_admin and company_id:
        await sio.emit('user_typing', payload, room=f"company_{company_id}")
    else:
        await sio.emit('user_typing', payload, room="admin_support")


async def broadcast_new_message(msg_data):
    """
    Utility for REST views to broadcast a message through Socket.IO
    """
    company_id = msg_data.get('company_id')
    if company_id:
        await sio.emit('new_message', msg_data, room=f"company_{company_id}")
    await sio.emit('new_message', msg_data, room="admin_support")


def broadcast_sync_message(event_name, data):
    """
    Sync bridge for Django REST framework views to broadcast socket events
    """
    import asyncio
    async def _emit():
        company_id = (data.get('company_id') or data.get('company')) if isinstance(data, dict) else None
        if company_id:
            await sio.emit(event_name, data, room=f"company_{company_id}")
        await sio.emit(event_name, data, room="admin_support")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_emit())
        else:
            loop.run_until_complete(_emit())
    except RuntimeError:
        asyncio.run(_emit())
    except Exception as e:
        logger.error(f"[Socket.IO] Broadcast error: {e}")
