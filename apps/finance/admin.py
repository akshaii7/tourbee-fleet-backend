from django.contrib import admin
from .models import BusinessSettings, SalaryCalculation, SalaryPayment, RentPayment


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'currency', 'default_daily_rent', 'contact_phone', 'contact_email')


@admin.register(SalaryCalculation)
class SalaryCalculationAdmin(admin.ModelAdmin):
    list_display = ('driver', 'period_start', 'period_end', 'status', 'total_gross_earnings', 'driver_share_50', 'net_payable_to_driver', 'created_at')
    list_filter = ('status',)
    search_fields = ('driver__user__first_name', 'driver__user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'period_start'
    raw_id_fields = ('driver', 'calculated_by')


@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ('driver', 'salary_calculation', 'amount', 'payment_method', 'payment_date', 'recorded_by')
    list_filter = ('payment_method',)
    search_fields = ('driver__user__first_name', 'driver__user__last_name')
    readonly_fields = ('created_at',)
    date_hierarchy = 'payment_date'
    raw_id_fields = ('driver', 'salary_calculation', 'recorded_by')


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'payment_date', 'amount_due', 'amount_paid', 'payment_method', 'recorded_by')
    list_filter = ('payment_method',)
    search_fields = ('driver__user__first_name', 'driver__user__last_name', 'vehicle__registration_number')
    readonly_fields = ('created_at',)
    date_hierarchy = 'payment_date'
    raw_id_fields = ('driver', 'vehicle', 'recorded_by')
