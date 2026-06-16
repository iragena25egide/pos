import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

print(f"Total users: {User.objects.count()}")
for u in User.objects.all():
    print(f"- {u.username} (is_superuser: {u.is_superuser})")

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("Created superuser: admin / admin123")
else:
    print("User 'admin' already exists. Resetting password to admin123...")
    u = User.objects.get(username='admin')
    u.set_password('admin123')
    u.save()
    print("Password reset for 'admin'.")
