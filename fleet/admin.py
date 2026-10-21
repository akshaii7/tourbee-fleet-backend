from django.contrib import admin
from .models import DailyCalculation


@admin.register(DailyCalculation)
class DailyCalculationAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'driver', 'vehicle', 'A', 'B', 'C', 'G', 'driver_share', 'company_share', 'J', 'status')
    list_filter = ('status', 'payment_mode', 'date')
    search_fields = ('driver__user__username', 'driver__user__first_name', 'driver__user__last_name', 'vehicle__registration_number')

