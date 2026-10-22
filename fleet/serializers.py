import os
from decimal import Decimal
from rest_framework import serializers
from .models import (
    DriverProfile, Vehicle, DailyEarning, DailyCalculation,
    CNGExpense, Refund, CompanyPayment, SalaryPayment,
    UploadedDocument, AuditLog, AccidentDeduction
)

class VehicleSerializer(serializers.ModelSerializer):
    assigned_driver_name = serializers.SerializerMethodField()
    assigned_driver_id = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    fuel_type = serializers.SerializerMethodField()
    insurance_status = serializers.SerializerMethodField()
    fitness_status = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = '__all__'

    def get_assigned_driver_name(self, obj):
        driver = getattr(obj, 'assigned_driver', None)
        if driver:
            return driver.user.get_full_name() or driver.user.username
        # Also check assigned_drivers in fleet
        first_fleet_driver = obj.assigned_drivers.first()
        if first_fleet_driver:
            return first_fleet_driver.user.get_full_name() or first_fleet_driver.user.username
        return None

    def get_assigned_driver_id(self, obj):
        driver = getattr(obj, 'assigned_driver', None)
        if driver:
            return driver.id
        first_fleet_driver = obj.assigned_drivers.first()
        return first_fleet_driver.id if first_fleet_driver else None

    def get_status(self, obj):
        return 'ACTIVE' if obj.is_active else 'INACTIVE'

    def get_fuel_type(self, obj):
        return 'CNG'

    def get_insurance_status(self, obj):
        return 'VALID'

    def get_fitness_status(self, obj):
        return 'VALID'

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

    def _make_absolute(self, url):
        if not url:
            return None
        if url.startswith('http://'):
            return 'https://' + url[7:]
        if url.startswith('https://'):
            return url
        base = os.getenv('BACKEND_BASE_URL', 'https://tourbee-fleet-backend-1.onrender.com').rstrip('/')
        clean_url = '/' + url.lstrip('/')
        return f"{base}{clean_url}"

    def get_cng_bill_url(self, obj):
        if obj.cng_bill_file:
            return self._make_absolute(obj.cng_bill_file.url)
        # Fallback to related CNGExpense on same date/driver if exists
        try:
            from .models import CNGExpense
            cng = CNGExpense.objects.filter(driver=obj.driver, date=obj.date).exclude(bill_file='').first()
            if cng and cng.bill_file:
                return self._make_absolute(cng.bill_file.url)
        except Exception:
            pass
        return None

    def get_uber_screenshot_url(self, obj):
        if obj.uber_screenshot_file:
            return self._make_absolute(obj.uber_screenshot_file.url)
        # Fallback to related DailyEarning if attached or on same date/driver
        try:
            if obj.daily_earning and obj.daily_earning.earnings_proof:
                return self._make_absolute(obj.daily_earning.earnings_proof.url)
            from .models import DailyEarning
            earning = DailyEarning.objects.filter(driver=obj.driver, date=obj.date).exclude(earnings_proof='').first()
            if earning and earning.earnings_proof:
                return self._make_absolute(earning.earnings_proof.url)
        except Exception:
            pass
        return None

    def to_internal_value(self, data):
        mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)
        request = self.context.get('request')
        if 'driver' not in mutable_data and request and request.user and not getattr(request.user, 'is_admin', False):
            from fleet.models import DriverProfile
            profile = DriverProfile.objects.filter(user=request.user).first()
            if profile:
                mutable_data['driver'] = profile.id

        if 'driver' in mutable_data and mutable_data['driver']:
            from fleet.models import DriverProfile
            raw_driver_id = getattr(mutable_data['driver'], 'pk', mutable_data['driver'])
            try:
                if DriverProfile.objects.filter(id=raw_driver_id).exists():
                    pass
                else:
                    from apps.drivers.models import Driver as AppDriver
                    app_driver = AppDriver.objects.filter(id=raw_driver_id).first()
                    if app_driver:
                        profile = DriverProfile.objects.filter(user_id=app_driver.user_id).first()
                        if profile:
                            mutable_data['driver'] = profile.id
                        else:
                            raise serializers.ValidationError({'driver': 'Driver has no fleet profile. Please contact admin.'})
                    else:
                        raise serializers.ValidationError({'driver': 'Driver has no fleet profile. Please contact admin.'})
            except (ValueError, TypeError):
                raise serializers.ValidationError({'driver': 'Driver has no fleet profile. Please contact admin.'})

        if 'vehicle' in mutable_data and mutable_data['vehicle']:
            from fleet.models import Vehicle as FleetVehicle
            raw_vehicle_id = getattr(mutable_data['vehicle'], 'pk', mutable_data['vehicle'])
            try:
                if FleetVehicle.objects.filter(id=raw_vehicle_id).exists():
                    pass
                else:
                    from apps.vehicles.models import Vehicle as AppVehicle
                    app_vehicle = AppVehicle.objects.filter(id=raw_vehicle_id).first()
                    if app_vehicle:
                        reg = app_vehicle.registration_number.strip().upper()
                        fleet_vehicle = FleetVehicle.objects.filter(
                            registration_number__iexact=reg
                        ).first()
                        if fleet_vehicle:
                            mutable_data['vehicle'] = fleet_vehicle.id
                        else:
                            raise serializers.ValidationError({'vehicle': 'Vehicle has no fleet record. Please contact admin.'})
                    else:
                        raise serializers.ValidationError({'vehicle': 'Vehicle has no fleet record. Please contact admin.'})
            except (ValueError, TypeError):
                raise serializers.ValidationError({'vehicle': 'Vehicle has no fleet record. Please contact admin.'})

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

