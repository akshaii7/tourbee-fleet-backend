#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Fail clearly if ADMIN_PASSWORD is missing
if [ -z "${ADMIN_PASSWORD}" ]; then
  echo "ERROR: ADMIN_PASSWORD environment variable is not set. Please set it in Render dashboard."
  exit 1
fi

python manage.py shell << 'EOF'
import os
import sys
from django.contrib.auth import get_user_model

password = os.environ.get('ADMIN_PASSWORD')
if not password:
    print("ERROR: ADMIN_PASSWORD environment variable is missing", file=sys.stderr)
    sys.exit(1)

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
