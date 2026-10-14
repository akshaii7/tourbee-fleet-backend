from rest_framework import serializers
from .models import BusinessSettings, SalaryCalculation, SalaryPayment, RentPayment

class BusinessSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessSettings
        fields = '__all__'

class SalaryPaymentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SalaryPayment
        fields = [
            'id', 'salary_calculation', 'driver', 'driver_name',
            'payment_date', 'amount', 'payment_method', 'transaction_reference',
            'receipt_file', 'notes', 'recorded_by', 'recorded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'recorded_by']

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return 'System'

class SalaryCalculationSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    driver_license = serializers.CharField(source='driver.license_number', read_only=True)
    calculated_by_name = serializers.SerializerMethodField()
    payments = SalaryPaymentSerializer(many=True, read_only=True)
    total_paid = serializers.SerializerMethodField()
    balance_payable = serializers.SerializerMethodField()

    class Meta:
        model = SalaryCalculation
        fields = [
            'id', 'driver', 'driver_name', 'driver_license',
            'period_start', 'period_end',
            'total_gross_earnings', 'total_commission', 'total_eligible_expenses',
            'distributable_profit', 'driver_share_50', 'company_share_50',
            'cash_collected_deduction', 'driver_reimbursements', 'net_payable_to_driver',
            'status', 'notes', 'calculated_by', 'calculated_by_name',
            'payments', 'total_paid', 'balance_payable',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'calculated_by']

    def get_calculated_by_name(self, obj):
        if obj.calculated_by:
            return obj.calculated_by.get_full_name() or obj.calculated_by.username
        return 'System'

    def get_total_paid(self, obj):
        return sum(p.amount for p in obj.payments.all())

    def get_balance_payable(self, obj):
        paid = sum(p.amount for p in obj.payments.all())
        return max(0, obj.net_payable_to_driver - paid)

class RentPaymentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    recorded_by_name = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()

    class Meta:
        model = RentPayment
        fields = [
            'id', 'driver', 'driver_name', 'vehicle', 'vehicle_reg',
            'payment_date', 'period_start', 'period_end',
            'daily_rate', 'days_count', 'amount_due', 'amount_paid',
            'outstanding_balance', 'payment_method', 'transaction_reference',
            'receipt_file', 'notes', 'recorded_by', 'recorded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'recorded_by']

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return 'System'

    def get_outstanding_balance(self, obj):
        return max(0, obj.amount_due - obj.amount_paid)
