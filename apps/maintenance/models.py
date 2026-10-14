from django.db import models
from django.conf import settings
from django.utils import timezone

class MaintenanceType(models.TextChoices):
    SCHEDULED_SERVICE = 'SCHEDULED_SERVICE', 'Periodic Scheduled Service'
    OIL_CHANGE = 'OIL_CHANGE', 'Engine Oil & Filter Change'
    BRAKE_CLUTCH = 'BRAKE_CLUTCH', 'Brake Pads / Clutch Work'
    TYRE_REPLACEMENT = 'TYRE_REPLACEMENT', 'Tyre Replacement / Alignment'
    CNG_KIT_INSPECTION = 'CNG_KIT_INSPECTION', 'CNG Kit Hydro-Test & Filter'
    BATTERY = 'BATTERY', 'Battery Service / Replacement'
    AC_SERVICE = 'AC_SERVICE', 'AC Compressor & Cooling Coil'
    ACCIDENT_BODYWORK = 'ACCIDENT_BODYWORK', 'Accident Repair / Bodywork'
    OTHER = 'OTHER', 'General Repairs & Spares'

class MaintenanceRecord(models.Model):
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, related_name='maintenance_records')
    date = models.DateField(default=timezone.localdate, db_index=True)
    maintenance_type = models.CharField(max_length=40, choices=MaintenanceType.choices, default=MaintenanceType.SCHEDULED_SERVICE)
    cost = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total garage service invoice amount (Company expense)")
    vendor_garage = models.CharField(max_length=150, help_text="Name of workshop or garage in Kerala")
    odometer_reading = models.PositiveIntegerField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)
    invoice_file = models.FileField(upload_to='maintenance_invoices/%Y/%m/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.vehicle.registration_number} - {self.get_maintenance_type_display()} (₹{self.cost}) on {self.date.strftime('%d-%m-%Y')}"
