from django.contrib import admin
from .models import ExpenseCategory, EarningsSubmission, ExpenseSubmission, SubmissionAttachment, AuditEvent


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_eligible_for_profit_sharing')
    search_fields = ('name', 'code')


class SubmissionAttachmentInline(admin.TabularInline):
    model = SubmissionAttachment
    extra = 0
    readonly_fields = ('uploaded_at', 'file_size', 'file_type')


@admin.register(EarningsSubmission)
class EarningsSubmissionAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'date', 'gross_earnings', 'net_earnings', 'cash_collected', 'trips_count', 'status')
    list_filter = ('status',)
    search_fields = ('driver__user__first_name', 'driver__user__last_name', 'vehicle__registration_number')
    readonly_fields = ('net_earnings', 'created_at', 'updated_at', 'reviewed_at')
    date_hierarchy = 'date'
    raw_id_fields = ('driver', 'vehicle', 'reviewed_by')
    inlines = [SubmissionAttachmentInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('driver', 'vehicle', 'date', 'status')
        }),
        ('Earnings', {
            'fields': ('gross_earnings', 'cash_collected', 'uber_commission', 'toll_included', 'other_deductions', 'net_earnings')
        }),
        ('Trip Info', {
            'fields': ('online_hours', 'trips_count', 'notes')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'rejection_reason', 'correction_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ExpenseSubmission)
class ExpenseSubmissionAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'category', 'date', 'amount', 'paid_by_driver', 'status')
    list_filter = ('status', 'category', 'paid_by_driver', 'is_operating_expense')
    search_fields = ('driver__user__first_name', 'driver__user__last_name', 'vehicle__registration_number', 'vendor_name')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')
    date_hierarchy = 'date'
    raw_id_fields = ('driver', 'vehicle', 'reviewed_by')
    inlines = [SubmissionAttachmentInline]


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('target_model', 'target_id', 'action', 'actor', 'previous_status', 'new_status', 'created_at')
    list_filter = ('target_model', 'action')
    search_fields = ('actor__username', 'notes')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
