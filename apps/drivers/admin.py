from django.contrib import admin
from .models import Driver


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'driver_type', 'license_number', 'license_expiry', 'assigned_vehicle', 'is_active', 'joining_date')
    list_filter = ('driver_type', 'is_active')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'license_number')
    raw_id_fields = ('user', 'assigned_vehicle')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'driver_type', 'is_active', 'joining_date', 'assigned_vehicle')
        }),
        ('License', {
            'fields': ('license_number', 'license_expiry')
        }),
        ('Financials', {
            'fields': ('daily_rent_amount',)
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone')
        }),
        ('Notes & Timestamps', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
