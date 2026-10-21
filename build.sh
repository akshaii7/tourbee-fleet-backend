#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
mkdir -p media media/cng_bills media/uber_screenshots media/receipts

# Force reset admin credentials on every deploy
# ADMIN_PASSWORD env var is intentionally IGNORED to prevent login lockout
export ADMIN_PASSWORD="TourBee@2026"
export ADMIN_USERNAME="admin"
export ADMIN_EMAIL="admin@tourbee.com"

python manage.py shell << 'EOF'
import os
from django.contrib.auth import get_user_model

User = get_user_model()
# Force hardcoded values — do NOT read from env to prevent lockout
password = 'TourBee@2026'
username = 'admin'
email = 'admin@tourbee.com'

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
