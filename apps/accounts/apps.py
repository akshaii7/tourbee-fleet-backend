from django.apps import AppConfig
from django.db.models.signals import post_migrate

def ensure_admin(sender, **kwargs):
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(username='admin').first() or User.objects.filter(email='admin@tourbee.com').first()
        if not user:
            user = User(username='admin', email='admin@tourbee.com')
        user.username = 'admin'
        user.email = 'admin@tourbee.com'
        user.set_password('TourBee@2026')
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
