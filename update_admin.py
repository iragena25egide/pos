import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

try:
    u = User.objects.get(username='admin')
    u.email = 'admin@nexus.rw'
    u.set_password('Nexus@admin!')
    u.save()
    print("Admin updated: admin / Nexus@admin! (email: admin@nexus.rw)")
except User.DoesNotExist:
    User.objects.create_superuser('admin', 'admin@nexus.rw', 'Nexus@admin!')
    print("Created superuser: admin / Nexus@admin! (email: admin@nexus.rw)")
