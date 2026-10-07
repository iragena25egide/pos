import os
import json
import urllib.request
import urllib.error
import logging

logger = logging.getLogger(__name__)

def send_otp_email(to_email: str, otp_code: str, owner_name: str = "Store Owner", company_name: str = "your store") -> bool:
    """
    Sends a branded 6-digit OTP email using the Resend API (HTTPS).
    Fallback to console logging if RESEND_API_KEY is not configured.
    """
    api_key = os.getenv('RESEND_API_KEY', '').strip()
    from_email = os.getenv('RESEND_FROM_EMAIL', 'Ziga POS <onboarding@resend.dev>').strip()

    subject = f"{otp_code} is your Ziga POS verification code"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Ziga POS Verification Code</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #0f172a; padding: 40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" max-width="520" style="max-width: 520px; background-color: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 36px 32px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);">
              
              <!-- Brand Header -->
              <tr>
                <td align="center" style="padding-bottom: 24px;">
                  <div style="display: inline-block; background: linear-gradient(135deg, #4f46e5, #06b6d4); padding: 10px 22px; border-radius: 12px;">
                    <span style="font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: 1px;">ZIGA POS</span>
                  </div>
                  <h1 style="color: #ffffff; font-size: 22px; font-weight: 700; margin: 20px 0 6px 0;">Verify your email address</h1>
                  <p style="color: #94a3b8; font-size: 14px; margin: 0;">Complete your store setup on Ziga POS</p>
                </td>
              </tr>

              <!-- Greeting & Body -->
              <tr>
                <td style="padding: 12px 0 20px 0;">
                  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin: 0 0 12px 0;">
                    Hello <strong style="color: #ffffff;">{owner_name}</strong>,
                  </p>
                  <p style="color: #cbd5e1; font-size: 15px; line-height: 1.6; margin: 0 0 20px 0;">
                    Thank you for creating an account for <strong style="color: #38bdf8;">{company_name}</strong>. Please use the 6-digit verification code below to verify your email address:
                  </p>
                </td>
              </tr>

              <!-- OTP Code Box -->
              <tr>
                <td align="center" style="padding: 10px 0 26px 0;">
                  <div style="background-color: #0f172a; border: 1px solid #475569; border-radius: 12px; padding: 18px 24px; display: inline-block; letter-spacing: 8px;">
                    <span style="font-family: 'Courier New', Courier, monospace; font-size: 34px; font-weight: 800; color: #38bdf8;">{otp_code}</span>
                  </div>
                  <p style="color: #64748b; font-size: 13px; margin: 12px 0 0 0;">
                    ⏱️ Code expires in <strong>10 minutes</strong>
                  </p>
                </td>
              </tr>

              <!-- Security Notice -->
              <tr>
                <td style="border-top: 1px solid #334155; padding-top: 20px;">
                  <p style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0;">
                    If you didn't request this verification code, you can safely ignore this email. Never share this code with anyone.
                  </p>
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td align="center" style="padding-top: 24px;">
                  <p style="color: #475569; font-size: 12px; margin: 0;">
                    © 2026 Ziga POS System. All rights reserved.
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    print("=" * 60)
    print(f"[ZIGA POS OTP Verification] Target: {to_email} | Code: {otp_code}")
    print("=" * 60)

    if not api_key:
        logger.warning(f"[Resend] RESEND_API_KEY is not set. OTP code logged to console for {to_email}.")
        return False

    # Send via Resend REST API (HTTPS endpoint: https://api.resend.com/emails)
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "resend-python/2.0.0"
    }
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    def _execute_post(ctx=None):
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        kwargs = {'timeout': 15}
        if ctx is not None:
            kwargs['context'] = ctx
        with urllib.request.urlopen(req, **kwargs) as response:
            return response.read().decode('utf-8')

    try:
        try:
            res_body = _execute_post()
        except urllib.error.URLError as url_err:
            if 'CERTIFICATE_VERIFY_FAILED' in str(url_err):
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                res_body = _execute_post(ctx=ctx)
            else:
                raise

        logger.info(f"[Resend] Successfully sent OTP email to {to_email}: {res_body}")
        print(f"✅ [Resend] Successfully sent OTP email to {to_email}: {res_body}")
        return True
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        logger.error(f"[Resend HTTPError] Status {e.code}: {error_msg}")
        print(f"❌ [Resend HTTPError] Status {e.code}: {error_msg}")
        return False
    except Exception as e:
        logger.error(f"[Resend Error] {str(e)}")
        print(f"❌ [Resend Error] {str(e)}")
        return False
