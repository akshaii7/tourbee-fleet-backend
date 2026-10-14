#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py migrate

# Create admin superuser if not exists
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@tourbee.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin1234')

if not User.objects.filter(username=username).exists():
    user = User.objects.create_superuser(username=username, email=email, password=password)
    user.role = 'ADMIN'
    user.is_active = True
    user.save()
    print(f"Superuser '{username}' created successfully with ADMIN role!")
else:
    user = User.objects.get(username=username)
    user.set_password(password)
    user.is_superuser = True
    user.is_staff = True
    user.is_active = True
    user.role = 'ADMIN'
    user.save()
    print(f"Superuser '{username}' password and ADMIN role updated successfully!")
EOF
