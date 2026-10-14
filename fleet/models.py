from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from .calculations import compute_daily_breakdown

class StatusChoices(models.TextChoices):
    PENDING = 'PENDING', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'

class PaymentMethodChoices(models.TextChoices):
    CASH = 'CASH', 'Cash'
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer (IMPS/NEFT)'
    UPI = 'UPI', 'UPI (Google Pay / PhonePe / Paytm)'
    OTHER = 'OTHER', 'Other'

class PaymentStatusChoices(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    PAID = 'PAID', 'Paid'

class PaymentModeChoices(models.TextChoices):
    REVENUE_SHARING = 'REVENUE_SHARING', '50% Profit-Sharing Mode'
    FIXED_RENT = 'FIXED_RENT', 'Fixed Daily Rent Mode'

class WorkingDayChoices(models.TextChoices):
    FULL_DAY = 'FULL_DAY', 'Full Day (₹1,200)'
    HALF_DAY = 'HALF_DAY', 'Half Day (₹650)'

class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fleet_driver_profile')
    payment_mode = models.CharField(
        max_length=30,
        choices=PaymentModeChoices.choices,
        default=PaymentModeChoices.REVENUE_SHARING,
        help_text="Driver compensation mode: 50% Revenue Sharing or Fixed Rent"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    license_number = models.CharField(max_length=50, unique=True)
    assigned_vehicle = models.ForeignKey('fleet.Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_drivers')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__first_name', 'user__username']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            from apps.drivers.models import Driver as AppDriver
            mode = AppDriver.DriverType.PROFIT_SHARING if self.payment_mode == PaymentModeChoices.REVENUE_SHARING else AppDriver.DriverType.DAILY_RENT
            app_veh = None
            if self.assigned_vehicle:
                from apps.vehicles.models import Vehicle as AppVehicle
                app_veh = AppVehicle.objects.filter(registration_number=self.assigned_vehicle.registration_number).first()
            
            AppDriver.objects.update_or_create(
                user=self.user,
                defaults={
                    'driver_type': mode,
                    'license_number': self.license_number,
                    'assigned_vehicle': app_veh,
                    'is_active': self.is_active,
                }
            )
        except Exception:
            pass

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        return f"{name} ({self.license_number})"

class Vehicle(models.Model):
    registration_number = models.CharField(max_length=30, unique=True)
    make = models.CharField(max_length=50, default='Maruti Suzuki')
    model = models.CharField(max_length=50, default='WagonR CNG')
    year = models.PositiveIntegerField(default=2023)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['registration_number']

    def __str__(self):
        return f"{self.registration_number} - {self.make} {self.model}"

class DailyEarning(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='daily_earnings')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='daily_earnings')
    date = models.DateField(db_index=True)

    total_uber_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Variable A")
    cash_collected = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Variable B")
    uber_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Variable D")
    refund = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Variable F")

    earnings_proof = models.FileField(upload_to='uber_proofs/%Y/%m/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING, db_index=True)
    admin_remarks = models.TextField(blank=True, null=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('driver', 'vehicle', 'date')
        ordering = ['-date', '-submitted_at']

    def __str__(self):
        return f"Earnings: {self.driver} | {self.date.strftime('%d-%m-%Y')} | ₹{self.total_uber_earnings}"

class CNGExpense(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='cng_expenses')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='cng_expenses')
    date = models.DateField(db_index=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Variable E")
    bill_file = models.FileField(upload_to='cng_bills/%Y/%m/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING, db_index=True)
    admin_remarks = models.TextField(blank=True, null=True)

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-submitted_at']

    def __str__(self):
        return f"CNG: {self.driver} | {self.date.strftime('%d-%m-%Y')} | ₹{self.amount} ({self.status})"

class Refund(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='refunds')
    date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Variable F")
    reference = models.CharField(max_length=150, blank=True, null=True)
    supporting_document = models.FileField(upload_to='refunds/%Y/%m/', blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Refund: {self.driver} | {self.date.strftime('%d-%m-%Y')} | ₹{self.amount}"

class DailyCalculation(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='daily_calculations')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='daily_calculations')
    date = models.DateField(db_index=True)

    payment_mode = models.CharField(
        max_length=30,
        choices=PaymentModeChoices.choices,
        default=PaymentModeChoices.REVENUE_SHARING
    )
    working_day_type = models.CharField(
        max_length=20,
        choices=WorkingDayChoices.choices,
        default=WorkingDayChoices.FULL_DAY,
        blank=True,
        null=True
    )

    # Named variables per specs:
    A = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Total Uber Earnings")
    B = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Cash Collected")
    C = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Wallet (A - B)")
    D = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Uber Charge")
    E = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="CNG Expense")
    F = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Refund")
    G = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Earnings after Expenses (A - D - E)")
    driver_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Driver Share (G / 2)")
    company_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Company Share (G / 2)")
    H = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Earnings after adding back Uber Charge (G + D)")
    I = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Amount after refund (H - F)")
    J = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Final Driver Payment to Company (I - abs(C) or Fixed Rent)")

    status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
        db_index=True
    )
    cng_bill_file = models.FileField(upload_to='cng_bills/%Y/%m/', blank=True, null=True)
    uber_screenshot_file = models.FileField(upload_to='uber_screenshots/%Y/%m/', blank=True, null=True)

    is_locked = models.BooleanField(default=False, help_text="Locked by admin after approval")
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_calculations')

    daily_earning = models.OneToOneField(DailyEarning, on_delete=models.SET_NULL, null=True, blank=True, related_name='calculation')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('driver', 'date')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Calc: {self.driver} | {self.date.strftime('%d-%m-%Y')} | J=₹{self.J}"

    def recalculate(self):
        if self.payment_mode == PaymentModeChoices.FIXED_RENT:
            # Mode 2: Fixed Daily Rent Mode
            # Half Day = ₹650, Full Day = ₹1,200
            rent_amt = Decimal('650.00') if self.working_day_type == WorkingDayChoices.HALF_DAY else Decimal('1200.00')
            self.J = rent_amt
            self.driver_share = Decimal('0.00')
            self.company_share = Decimal('0.00')
            self.A = Decimal('0.00')
            self.B = Decimal('0.00')
            self.C = Decimal('0.00')
            self.D = Decimal('0.00')
            self.E = Decimal('0.00')
            self.F = Decimal('0.00')
            self.G = Decimal('0.00')
            self.H = Decimal('0.00')
            self.I = Decimal('0.00')
        else:
            # Mode 1: 50% Profit-Sharing Mode
            result = compute_daily_breakdown(
                total_uber_earnings=self.A,
                passenger_cash_collected=self.B,
                expenses=self.D,
                cng_expense=self.E,
                refund=self.F
            )
            self.C = result['wallet_difference']
            self.G = result['profit_amount']
            self.driver_share = result['driver_salary']
            self.company_share = result['tourbee_share']
            self.H = result['initial_settlement_amount']
            self.I = result['amount_after_refund']
            self.J = result['final_gpay_amount']

    def save(self, *args, **kwargs):
        self.recalculate()
        super().save(*args, **kwargs)

    @property
    def remaining_company_payment(self):
        if self.status == PaymentStatusChoices.PAID:
            return Decimal('0.00')
        paid = self.company_payments.filter(status=PaymentStatusChoices.PAID).aggregate(models.Sum('amount'))['amount__sum'] or Decimal('0.00')
        return max(Decimal('0.00'), self.J - paid)

    @property
    def payment_status(self):
        return self.status

class CompanyPayment(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='company_payments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name='company_payments')
    date = models.DateField(db_index=True)
    daily_calculation = models.ForeignKey(DailyCalculation, on_delete=models.CASCADE, related_name='company_payments', null=True, blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethodChoices.choices, default=PaymentMethodChoices.UPI)
    transaction_reference = models.CharField(max_length=150, blank=True, null=True)
    proof_file = models.FileField(upload_to='company_payments/%Y/%m/', blank=True, null=True)

    status = models.CharField(max_length=20, choices=PaymentStatusChoices.choices, default=PaymentStatusChoices.PENDING, db_index=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_company_payments')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Company Payment: {self.driver} | {self.date.strftime('%d-%m-%Y')} | ₹{self.amount} [{self.status}]"

class SalaryPayment(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='salary_credits')
    month = models.DateField(help_text="First day of the month this salary credit applies to (e.g. 2026-10-01)", db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    payment_date = models.DateField(default=timezone.localdate)
    payment_method = models.CharField(max_length=20, choices=PaymentMethodChoices.choices, default=PaymentMethodChoices.BANK_TRANSFER)
    transaction_reference = models.CharField(max_length=150, blank=True, null=True)
    receipt_file = models.FileField(upload_to='salary_receipts/%Y/%m/', blank=True, null=True)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_salary_payments')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"Salary Payment: {self.driver} | {self.payment_date.strftime('%d-%m-%Y')} | ₹{self.amount}"

class AccidentDeduction(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='deductions')
    date = models.DateField(default=timezone.localdate, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Deduction amount (₹)")
    reason = models.CharField(max_length=255, help_text="Reason / Description (e.g. Accident damage, Vehicle damage)")
    supporting_document = models.FileField(upload_to='deductions/%Y/%m/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.APPROVED, db_index=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_deductions')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"Deduction: {self.driver} | {self.date.strftime('%d-%m-%Y')} | ₹{self.amount} - {self.reason}"

class UploadedDocument(models.Model):
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=150)
    document_type = models.CharField(max_length=50, default='GENERAL')
    file = models.FileField(upload_to='driver_documents/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.driver}"

class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    target_model = models.CharField(max_length=50)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    previous_state = models.JSONField(null=True, blank=True)
    new_state = models.JSONField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%d-%m-%Y %H:%M')}] {self.user} - {self.action} on {self.target_model} #{self.target_id}"
