from rest_framework import serializers
from .models import (
    DriverProfile, Vehicle, DailyEarning, DailyCalculation,
    CNGExpense, Refund, CompanyPayment, SalaryPayment,
    UploadedDocument, AuditLog, AccidentDeduction
)

class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'

class DriverProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    assigned_vehicle_reg = serializers.CharField(source='assigned_vehicle.registration_number', read_only=True)

    class Meta:
        model = DriverProfile
        fields = [
            'id', 'user', 'username', 'full_name', 'email', 'phone',
            'payment_mode', 'license_number', 'assigned_vehicle', 'assigned_vehicle_reg',
            'is_active', 'created_at', 'updated_at'
        ]

class DailyCalculationSerializer(serializers.ModelSerializer):
    driver = serializers.PrimaryKeyRelatedField(queryset=DriverProfile.objects.all(), required=False)
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)
    driver_phone = serializers.CharField(source='driver.phone', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    remaining_payment = serializers.DecimalField(source='remaining_company_payment', max_digits=12, decimal_places=2, read_only=True)
    
    # Descriptive aliases for 50% profit-sharing calculation
    total_uber_earnings = serializers.DecimalField(source='A', max_digits=12, decimal_places=2, required=False)
    passenger_cash_collected = serializers.DecimalField(source='B', max_digits=12, decimal_places=2, required=False)
    wallet_difference = serializers.DecimalField(source='C', max_digits=12, decimal_places=2, read_only=True)
    expenses = serializers.DecimalField(source='D', max_digits=12, decimal_places=2, required=False)
    cng_expense = serializers.DecimalField(source='E', max_digits=12, decimal_places=2, required=False)
    refund = serializers.DecimalField(source='F', max_digits=12, decimal_places=2, required=False)
    profit_amount = serializers.DecimalField(source='G', max_digits=12, decimal_places=2, read_only=True)
    driver_salary = serializers.DecimalField(source='driver_share', max_digits=12, decimal_places=2, read_only=True)
    tourbee_share = serializers.DecimalField(source='company_share', max_digits=12, decimal_places=2, read_only=True)
    final_gpay_amount = serializers.DecimalField(source='J', max_digits=12, decimal_places=2, read_only=True)
    rent_due = serializers.SerializerMethodField()

    cng_bill_url = serializers.SerializerMethodField()
    uber_screenshot_url = serializers.SerializerMethodField()

    def get_rent_due(self, obj):
        if obj.payment_mode == 'FIXED_RENT':
            return '650.00' if obj.working_day_type == 'HALF_DAY' else '1200.00'
        return '0.00'

    def get_cng_bill_url(self, obj):
        if obj.cng_bill_file:
            url = obj.cng_bill_file.url
            request = self.context.get('request')
            if request and url.startswith('/'):
                return request.build_absolute_uri(url)
            return url
        return None

    def get_uber_screenshot_url(self, obj):
        if obj.uber_screenshot_file:
            url = obj.uber_screenshot_file.url
            request = self.context.get('request')
            if request and url.startswith('/'):
                return request.build_absolute_uri(url)
            return url
        return None

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        request = self.context.get('request')
        if 'driver' not in mutable_data and request and request.user and not getattr(request.user, 'is_admin', False):
            from fleet.models import DriverProfile
            profile = DriverProfile.objects.filter(user=request.user).first()
            if profile:
                mutable_data['driver'] = profile.id

        # Support both working_day and working_day_type key names
        if 'working_day' in mutable_data and 'working_day_type' not in mutable_data:
            mutable_data['working_day_type'] = mutable_data.pop('working_day')

        if 'total_uber_earnings' in mutable_data and 'A' not in mutable_data:
            mutable_data['A'] = mutable_data['total_uber_earnings']
        if 'passenger_cash_collected' in mutable_data and 'B' not in mutable_data:
            mutable_data['B'] = mutable_data['passenger_cash_collected']
        if 'expenses' in mutable_data and 'D' not in mutable_data:
            mutable_data['D'] = mutable_data['expenses']
        if 'cng_expense' in mutable_data and 'E' not in mutable_data:
            mutable_data['E'] = mutable_data['cng_expense']
        if 'refund' in mutable_data and 'F' not in mutable_data:
            mutable_data['F'] = mutable_data['refund']
        return super().to_internal_value(mutable_data)

    class Meta:
        model = DailyCalculation
        fields = [
            'id', 'driver', 'driver_name', 'driver_phone', 'vehicle', 'vehicle_reg', 'date',
            'payment_mode', 'working_day_type', 'status',
            'A', 'B', 'C', 'D', 'E', 'F', 'G',
            'driver_share', 'company_share', 'H', 'I', 'J',
            'total_uber_earnings', 'passenger_cash_collected', 'wallet_difference',
            'expenses', 'cng_expense', 'refund', 'profit_amount',
            'driver_salary', 'tourbee_share', 'final_gpay_amount', 'rent_due',
            'cng_bill_file', 'uber_screenshot_file', 'cng_bill_url', 'uber_screenshot_url',
            'is_locked', 'locked_at', 'locked_by', 'daily_earning',
            'remaining_payment', 'payment_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'C', 'G', 'driver_share', 'company_share', 'H', 'I', 'J',
            'wallet_difference', 'profit_amount', 'driver_salary', 'tourbee_share', 'final_gpay_amount',
            'payment_status', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'driver': {'required': False}
        }

class DailyEarningSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = DailyEarning
        fields = '__all__'

class CNGExpenseSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = CNGExpense
        fields = '__all__'

class RefundSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)

    class Meta:
        model = Refund
        fields = '__all__'

class CompanyPaymentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = CompanyPayment
        fields = '__all__'

class SalaryPaymentSerializer(serializers.ModelSerializer):
    """
    Salary payment (existing SalaryPayment model).

    ``amount`` is validated here for shape (> 0, max 2 decimals); the outstanding-balance
    check happens inside ``fleet.salary.record_salary_payment`` under a row lock.
    ``month`` is optional and defaults to the month of ``payment_date``.
    """
    driver_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    month = serializers.DateField(required=False)
    idempotency_key = serializers.CharField(max_length=64, required=False, allow_blank=True, write_only=True)

    def get_driver_name(self, obj):
        return obj.driver.user.get_full_name() or obj.driver.user.username

    def get_recorded_by_name(self, obj):
        return (obj.recorded_by.get_full_name() or obj.recorded_by.username) if obj.recorded_by else None

    def get_status(self, obj):
        # Every stored salary payment is a completed (paid) transfer.
        return 'PAID'

    class Meta:
        model = SalaryPayment
        fields = [
            'id', 'driver', 'driver_name', 'month', 'amount', 'payment_date',
            'payment_method', 'transaction_reference', 'notes', 'receipt_file',
            'status', 'recorded_by', 'recorded_by_name', 'idempotency_key', 'created_at',
        ]
        read_only_fields = ['id', 'recorded_by', 'created_at']

class UploadedDocumentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)

    class Meta:
        model = UploadedDocument
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = '__all__'

class AccidentDeductionSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.user.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.username', read_only=True)

    class Meta:
        model = AccidentDeduction
        fields = '__all__'

