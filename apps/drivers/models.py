from django.db import models
from django.conf import settings
from django.utils import timezone

class Driver(models.Model):
    class DriverType(models.TextChoices):
        PROFIT_SHARING = 'PROFIT_SHARING', '50% Profit-Sharing Mode'
        DAILY_RENT = 'DAILY_RENT', 'Fixed Daily Rent Mode'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='driver_profile'
    )
    driver_type = models.CharField(
        max_length=20,
        choices=DriverType.choices,
        default=DriverType.PROFIT_SHARING
    )
    license_number = models.CharField(max_length=50, unique=True)
    license_expiry = models.DateField(blank=True, null=True)
    daily_rent_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=800.00,
        help_text="Configurable daily rent for rent-based drivers"
    )
    assigned_vehicle = models.OneToOneField(
        'vehicles.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_driver'
    )
    is_active = models.BooleanField(default=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    upi_id = models.CharField(max_length=50, blank=True, null=True)
    
    joining_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            from fleet.models import DriverProfile as FleetProfile, Vehicle as FleetVehicle, PaymentModeChoices
            mode = PaymentModeChoices.REVENUE_SHARING if self.driver_type == self.DriverType.PROFIT_SHARING else PaymentModeChoices.FIXED_RENT
            fleet_veh = None
            if self.assigned_vehicle:
                fleet_veh = FleetVehicle.objects.filter(registration_number=self.assigned_vehicle.registration_number).first()
            
            FleetProfile.objects.update_or_create(
                user=self.user,
                defaults={
                    'payment_mode': mode,
                    'phone': self.user.phone_number or '',
                    'license_number': self.license_number,
                    'assigned_vehicle': fleet_veh,
                    'is_active': self.is_active,
                }
            )
        except Exception:
            pass

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} [{self.get_driver_type_display()}]"

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def phone_number(self):
        return self.user.phone_number

    @property
    def email(self):
        return self.user.email
