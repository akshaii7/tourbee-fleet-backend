from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

class BusinessSettings(models.Model):
    company_name = models.CharField(max_length=150, default='TourBee Kerala Fleet Pvt Ltd')
    currency = models.CharField(max_length=10, default='INR')
    currency_symbol = models.CharField(max_length=5, default='₹')
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    default_driver_profit_share_pct = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    default_company_profit_share_pct = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    default_daily_rent = models.DecimalField(max_digits=10, decimal_places=2, default=800.00)
    contact_phone = models.CharField(max_length=20, default='+91 98470 12345')
    contact_email = models.EmailField(default='operations@tourbee.in')
    address = models.TextField(default='MG Road, Ernakulam, Kochi, Kerala - 682016')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Business Settings'

    def __str__(self):
        return self.company_name

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

class CalculationStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    FINALIZED = 'FINALIZED', 'Finalized'
    PAID = 'PAID', 'Fully Paid'

class SalaryCalculation(models.Model):
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE, related_name='salary_calculations')
    period_start = models.DateField(db_index=True)
    period_end = models.DateField(db_index=True)
    
    total_gross_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_eligible_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    distributable_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    driver_share_50 = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    company_share_50 = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    cash_collected_deduction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Cash collected directly from riders, deducted from driver payout"
    )
    driver_reimbursements = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Out-of-pocket expenses paid by driver to be reimbursed"
    )
    net_payable_to_driver = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=CalculationStatus.choices, default=CalculationStatus.DRAFT)
    notes = models.TextField(blank=True, null=True)
    
    calculated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['driver', 'period_start', 'period_end']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Salary: {self.driver.full_name} ({self.period_start.strftime('%d-%m-%Y')} to {self.period_end.strftime('%d-%m-%Y')}) - ₹{self.net_payable_to_driver}"

    def clean(self):
        if self.driver.driver_type != 'PROFIT_SHARING':
            raise ValidationError("Salary profit-sharing calculation is only applicable for PROFIT_SHARING drivers.")

class PaymentMethod(models.TextChoices):
    UPI = 'UPI', 'UPI (Google Pay / PhonePe)'
    BANK_TRANSFER = 'BANK_TRANSFER', 'IMPS / NEFT Bank Transfer'
    CASH = 'CASH', 'Cash'
    CHEQUE = 'CHEQUE', 'Cheque'

class SalaryPayment(models.Model):
    salary_calculation = models.ForeignKey(SalaryCalculation, on_delete=models.CASCADE, related_name='payments')
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE, related_name='salary_payments')
    payment_date = models.DateField(default=timezone.localdate)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.UPI)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True, help_text="UTR or UPI transaction ID")
    receipt_file = models.FileField(upload_to='payment_receipts/%Y/%m/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['driver', 'payment_date']),
            models.Index(fields=['payment_date']),
        ]

    def __str__(self):
        return f"Salary Payment: {self.driver.full_name} - ₹{self.amount} ({self.payment_date.strftime('%d-%m-%Y')})"

class RentPayment(models.Model):
    driver = models.ForeignKey('drivers.Driver', on_delete=models.CASCADE, related_name='rent_payments')
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.CASCADE, related_name='rent_payments')
    payment_date = models.DateField(default=timezone.localdate)
    period_start = models.DateField()
    period_end = models.DateField()
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=800.00)
    days_count = models.PositiveIntegerField(default=1)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.UPI)
    transaction_reference = models.CharField(max_length=100, blank=True, null=True)
    receipt_file = models.FileField(upload_to='rent_receipts/%Y/%m/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['driver', 'payment_date']),
            models.Index(fields=['vehicle', 'payment_date']),
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        return f"Rent: {self.driver.full_name} - Paid ₹{self.amount_paid} of ₹{self.amount_due}"

    def clean(self):
        if self.driver.driver_type != 'DAILY_RENT':
            raise ValidationError("Rent payments are only applicable for DAILY_RENT drivers.")
