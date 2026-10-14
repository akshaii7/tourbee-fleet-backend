from rest_framework import serializers
from .models import (
    ExpenseCategory,
    EarningsSubmission,
    ExpenseSubmission,
    SubmissionAttachment,
    AuditEvent,
    SubmissionStatus
)
from apps.drivers.models import Driver
from apps.vehicles.models import Vehicle

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = '__all__'

class SubmissionAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionAttachment
        fields = ['id', 'file', 'file_url', 'file_name', 'file_size', 'file_type', 'uploaded_at']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

class AuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'target_model', 'target_id', 'actor', 'actor_name',
            'action', 'previous_status', 'new_status', 'notes', 'created_at'
        ]

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.username
        return 'System'

class EarningsSubmissionSerializer(serializers.ModelSerializer):
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False, allow_null=True)
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all(), required=False, allow_null=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    driver_type = serializers.CharField(source='driver.driver_type', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    vehicle_name = serializers.SerializerMethodField()
    attachments = SubmissionAttachmentSerializer(many=True, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    audit_logs = serializers.SerializerMethodField()

    class Meta:
        model = EarningsSubmission
        fields = [
            'id', 'driver', 'driver_name', 'driver_type', 'vehicle', 'vehicle_reg', 'vehicle_name',
            'date', 'online_hours', 'trips_count', 'gross_earnings', 'cash_collected',
            'uber_commission', 'toll_included', 'other_deductions', 'net_earnings',
            'notes', 'status', 'rejection_reason', 'correction_notes',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at',
            'attachments', 'audit_logs', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'net_earnings', 'status', 'rejection_reason',
            'correction_notes', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at'
        ]
        validators = []

    def validate(self, attrs):
        request = self.context.get('request')
        driver = attrs.get('driver')
        if not driver and request and hasattr(request.user, 'driver_profile'):
            driver = request.user.driver_profile
        sub_date = attrs.get('date')
        if driver and sub_date:
            qs = EarningsSubmission.objects.filter(driver=driver, date=sub_date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({'date': 'An earnings submission already exists for this driver on this date.'})
        return attrs

    def get_vehicle_name(self, obj):
        return f"{obj.vehicle.make} {obj.vehicle.model}"

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_audit_logs(self, obj):
        logs = AuditEvent.objects.filter(target_model='EarningsSubmission', target_id=obj.id)
        return AuditEventSerializer(logs, many=True).data

class ExpenseSubmissionSerializer(serializers.ModelSerializer):
    driver = serializers.PrimaryKeyRelatedField(queryset=Driver.objects.all(), required=False, allow_null=True)
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all(), required=False, allow_null=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    driver_type = serializers.CharField(source='driver.driver_type', read_only=True)
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_eligible_for_profit_sharing = serializers.BooleanField(source='category.is_eligible_for_profit_sharing', read_only=True)
    attachments = SubmissionAttachmentSerializer(many=True, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    audit_logs = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseSubmission
        fields = [
            'id', 'driver', 'driver_name', 'driver_type', 'vehicle', 'vehicle_reg',
            'category', 'category_name', 'is_eligible_for_profit_sharing',
            'date', 'amount', 'odometer_reading', 'fuel_quantity_kg_or_l',
            'vendor_name', 'description', 'paid_by_driver', 'is_operating_expense',
            'status', 'rejection_reason', 'correction_notes',
            'reviewed_by', 'reviewed_by_name', 'reviewed_at',
            'attachments', 'audit_logs', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'rejection_reason', 'correction_notes',
            'reviewed_by', 'reviewed_at', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'driver': {'required': False}
        }

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_audit_logs(self, obj):
        logs = AuditEvent.objects.filter(target_model='ExpenseSubmission', target_id=obj.id)
        return AuditEventSerializer(logs, many=True).data
