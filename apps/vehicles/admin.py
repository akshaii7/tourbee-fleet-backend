from django.contrib import admin
from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'make', 'model', 'year', 'fuel_type', 'status', 'insurance_expiry', 'fitness_expiry', 'current_odometer')
    list_filter = ('fuel_type', 'status', 'make')
    search_fields = ('registration_number', 'make', 'model', 'rc_number', 'insurance_policy_no')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Vehicle Details', {
            'fields': ('registration_number', 'make', 'model', 'year', 'fuel_type', 'status')
        }),
        ('Documents', {
            'fields': ('rc_number', 'insurance_policy_no', 'insurance_expiry', 'fitness_expiry', 'pollution_expiry')
        }),
        ('Operational', {
            'fields': ('current_odometer', 'daily_rent_rate', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
