"""
TourBee Fleet Manager - Secure Admin Account Creation Command

Usage:
    python manage.py create_admin

This command securely creates the TourBee admin account with ADMIN role.
Password is entered interactively and never stored in code or logs.
If admin@tourbee.in / admin already exists, it updates role without
creating a duplicate.
"""
import getpass
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class Command(BaseCommand):
    help = "Securely create (or update) the TourBee ADMIN account."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(
            "\n🐝 TourBee Fleet Manager — Admin Account Setup\n"
            + "=" * 50
        ))

        username = "admin"
        email = "admin@tourbee.in"

        existing = User.objects.filter(username=username).first()
        if existing:
            self.stdout.write(self.style.WARNING(
                f"\n⚠️  Account '{username}' already exists.\n"
                f"   Email  : {existing.email}\n"
                f"   Role   : {existing.role}\n"
                f"   Active : {existing.is_active}\n"
            ))
            update = input("Do you want to reset the password for this account? [y/N]: ").strip().lower()
            if update != 'y':
                self.stdout.write(self.style.SUCCESS("✓ No changes made. Admin account is ready."))
                return
            user = existing
            # Ensure correct role and staff settings regardless
            user.role = User.Role.ADMIN
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.email = email
        else:
            self.stdout.write(self.style.NOTICE(
                f"\nCreating admin account:\n"
                f"  Username : {username}\n"
                f"  Email    : {email}\n"
                f"  Role     : ADMIN\n"
            ))
            user = User(username=username, email=email)
            user.role = User.Role.ADMIN
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True

        # Secure password entry — never logged or echoed
        while True:
            password = getpass.getpass(prompt="\nEnter admin password (min 8 chars): ")
            if not password:
                self.stderr.write("❌ Password cannot be empty.")
                continue
            password2 = getpass.getpass(prompt="Confirm password              : ")
            if password != password2:
                self.stderr.write("❌ Passwords do not match. Try again.")
                continue
            try:
                validate_password(password, user)
                break
            except ValidationError as e:
                self.stderr.write("❌ Password too weak:\n" + "\n".join(f"   • {err}" for err in e.messages))

        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Admin account created / updated successfully!\n"
            f"   Username : {user.username}\n"
            f"   Email    : {user.email}\n"
            f"   Role     : {user.role}\n\n"
            f"🔐 You can now log in at http://localhost:5173/login\n"
        ))
