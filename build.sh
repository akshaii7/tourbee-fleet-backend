#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Set default ADMIN_PASSWORD if not provided in Render dashboard
ADMIN_PASSWORD="${ADMIN_PASSWORD:-adminpassword123}"
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@tourbee.com}"

python manage.py shell << 'EOF'
import os
import sys
from django.contrib.auth import get_user_model

password = os.environ.get('ADMIN_PASSWORD', 'adminpassword123')

User = get_user_model()
username = os.environ.get('ADMIN_USERNAME', 'admin')
email = os.environ.get('ADMIN_EMAIL', 'admin@tourbee.com')

# Clean up or get user
user = User.objects.filter(username=username).first()
if not user:
    user = User.objects.filter(email=email).first()

if user:
    user.username = username
    user.email = email
else:
    user = User(username=username, email=email)

user.set_password(password)
user.is_superuser = True
user.is_staff = True
user.is_active = True
user.role = 'ADMIN'
user.save()

print(f"ADMIN_READY: username='{user.username}' password is set!")
EOF
