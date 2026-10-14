from django.contrib import admin
from .models import MaintenanceRecord


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'maintenance_type', 'date', 'cost', 'vendor_garage', 'odometer_reading', 'recorded_by')
    list_filter = ('maintenance_type',)
    search_fields = ('vehicle__registration_number', 'vendor_garage', 'invoice_number')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    raw_id_fields = ('vehicle', 'recorded_by')
