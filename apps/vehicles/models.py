from django.db import models
from django.utils import timezone

class Vehicle(models.Model):
    class FuelType(models.TextChoices):
        CNG = 'CNG', 'CNG'
        PETROL = 'PETROL', 'Petrol'
        DIESEL = 'DIESEL', 'Diesel'
        EV = 'EV', 'Electric (EV)'

    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active / On Road'
        MAINTENANCE = 'MAINTENANCE', 'In Garage / Maintenance'
        INACTIVE = 'INACTIVE', 'Inactive / Grounded'

    registration_number = models.CharField(max_length=20, unique=True, db_index=True)
    make = models.CharField(max_length=50, default='Maruti Suzuki')
    model = models.CharField(max_length=50, default='WagonR CNG')
    year = models.PositiveIntegerField(default=2023)
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices, default=FuelType.CNG)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    rc_number = models.CharField(max_length=50, blank=True, null=True)
    insurance_policy_no = models.CharField(max_length=50, blank=True, null=True)
    insurance_expiry = models.DateField(blank=True, null=True)
    fitness_expiry = models.DateField(blank=True, null=True)
    pollution_expiry = models.DateField(blank=True, null=True)
    
    current_odometer = models.PositiveIntegerField(default=0)
    daily_rent_rate = models.DecimalField(max_digits=10, decimal_places=2, default=800.00)
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['registration_number']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['fuel_type']),
            models.Index(fields=['status', 'fuel_type']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            from fleet.models import Vehicle as FleetVehicle
            FleetVehicle.objects.update_or_create(
                registration_number=self.registration_number,
                defaults={
                    'make': self.make or 'Maruti Suzuki',
                    'model': self.model or 'WagonR CNG',
                    'year': self.year or 2023,
                    'is_active': self.status == self.Status.ACTIVE,
                }
            )
        except Exception:
            pass

    def delete(self, *args, **kwargs):
        reg = self.registration_number
        try:
            from fleet.models import Vehicle as FleetVehicle
            FleetVehicle.objects.filter(registration_number=reg).delete()
        except Exception:
            try:
                from fleet.models import Vehicle as FleetVehicle
                FleetVehicle.objects.filter(registration_number=reg).update(is_active=False)
            except Exception:
                pass
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.registration_number} ({self.make} {self.model})"

    @property
    def assigned_driver_profile(self):
        return getattr(self, 'assigned_driver', None)

    @property
    def insurance_status(self):
        if not self.insurance_expiry:
            return 'UNKNOWN'
        delta = (self.insurance_expiry - timezone.localdate()).days
        if delta < 0:
            return 'EXPIRED'
        if delta <= 15:
            return 'EXPIRING_SOON'
        return 'VALID'

    @property
    def fitness_status(self):
        if not self.fitness_expiry:
            return 'UNKNOWN'
        delta = (self.fitness_expiry - timezone.localdate()).days
        if delta < 0:
            return 'EXPIRED'
        if delta <= 15:
            return 'EXPIRING_SOON'
        return 'VALID'
