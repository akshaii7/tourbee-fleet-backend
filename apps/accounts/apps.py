import os
from django.apps import AppConfig
from django.db.models.signals import post_migrate

def ensure_admin(sender, **kwargs):
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        username = os.environ.get('ADMIN_USERNAME', 'admin')
        email = os.environ.get('ADMIN_EMAIL', 'admin@tourbee.com')
        password = os.environ.get('ADMIN_PASSWORD', 'TourBee@2026')

        user = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()
        if not user:
            user = User(username=username, email=email)
        user.username = username
        user.email = email
        user.set_password(password)
        user.role = 'ADMIN'
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
    except Exception:
        pass

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        post_migrate.connect(ensure_admin, sender=self)
