from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

class SubmissionStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    CORRECTION_REQUESTED = 'CORRECTION_REQUESTED', 'Correction Requested'

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    is_eligible_for_profit_sharing = models.BooleanField(
        default=True,
        help_text="Whether this expense category is deducted from driver profit sharing calculation"
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Expense Categories'

    def __str__(self):
        return f"{self.name} ({'Eligible' if self.is_eligible_for_profit_sharing else 'Company Only'})"

class EarningsSubmission(models.Model):
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE, related_name='earnings_submissions')
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, related_name='earnings_submissions')
    date = models.DateField(db_index=True)
    
    online_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    trips_count = models.PositiveIntegerField(default=0)
    
    gross_earnings = models.DecimalField(max_digits=10, decimal_places=2, help_text="Gross Uber earnings before commissions")
    cash_collected = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Cash collected by driver from riders")
    uber_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Uber platform commission fee")
    toll_included = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Toll fares included in Uber earnings")
    other_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Uber tax / other platform deductions")
    net_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Gross - Uber Commission - deductions")
    
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING, db_index=True)
    rejection_reason = models.TextField(blank=True, null=True)
    correction_notes = models.TextField(blank=True, null=True)
    
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_earnings')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('driver', 'date')
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['driver', 'date']),
            models.Index(fields=['vehicle', 'date']),
            models.Index(fields=['status', 'date']),
        ]

    def __str__(self):
        return f"Earnings: {self.driver.full_name} | {self.date.strftime('%d-%m-%Y')} | ₹{self.gross_earnings} [{self.status}]"

    def save(self, *args, **kwargs):
        from decimal import Decimal
        gross = Decimal(str(self.gross_earnings or '0'))
        comm = Decimal(str(self.uber_commission or '0'))
        deductions = Decimal(str(self.other_deductions or '0'))
        self.net_earnings = gross - comm - deductions
        super().save(*args, **kwargs)

class ExpenseSubmission(models.Model):
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE, related_name='expense_submissions')
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, related_name='expense_submissions')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    date = models.DateField(db_index=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    odometer_reading = models.PositiveIntegerField(null=True, blank=True)
    fuel_quantity_kg_or_l = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="CNG (kg) or Fuel (litres)")
    vendor_name = models.CharField(max_length=150, blank=True, null=True, help_text="Fuel pump station or shop name")
    description = models.TextField(blank=True, null=True)
    
    paid_by_driver = models.BooleanField(default=True, help_text="Was this paid directly by driver cash/UPI?")
    is_operating_expense = models.BooleanField(default=True)
    
    status = models.CharField(max_length=30, choices=SubmissionStatus.choices, default=SubmissionStatus.PENDING, db_index=True)
    rejection_reason = models.TextField(blank=True, null=True)
    correction_notes = models.TextField(blank=True, null=True)
    
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_expenses')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['driver', 'date']),
            models.Index(fields=['vehicle', 'date']),
            models.Index(fields=['category', 'date']),
            models.Index(fields=['status', 'date']),
        ]

    def __str__(self):
        return f"Expense: {self.category.name} | {self.driver.full_name} | ₹{self.amount} [{self.status}]"

def attachment_upload_path(instance, filename):
    today = timezone.localdate()
    return f"receipts/{today.year}/{today.month:02d}/{filename}"

class SubmissionAttachment(models.Model):
    earnings_submission = models.ForeignKey(
        EarningsSubmission,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments'
    )
    expense_submission = models.ForeignKey(
        ExpenseSubmission,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments'
    )
    file = models.FileField(upload_to=attachment_upload_path)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)
    file_type = models.CharField(max_length=50, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment: {self.file_name} ({self.file_size} bytes)"

class AuditEvent(models.Model):
    target_model = models.CharField(max_length=50, db_index=True)
    target_id = models.PositiveIntegerField(db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50)
    previous_status = models.CharField(max_length=50, blank=True, null=True)
    new_status = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Audit: {self.target_model} #{self.target_id} {self.action} by {self.actor} at {self.created_at}"
