from rest_framework import serializers
from .models import MaintenanceRecord

class MaintenanceRecordSerializer(serializers.ModelSerializer):
    vehicle_reg = serializers.CharField(source='vehicle.registration_number', read_only=True)
    vehicle_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    invoice_file_url = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceRecord
        fields = [
            'id', 'vehicle', 'vehicle_reg', 'vehicle_name', 'date',
            'maintenance_type', 'cost', 'vendor_garage', 'odometer_reading',
            'invoice_number', 'invoice_file', 'invoice_file_url', 'notes',
            'recorded_by', 'recorded_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'recorded_by']

    def get_vehicle_name(self, obj):
        return f"{obj.vehicle.make} {obj.vehicle.model}"

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return 'System'

    def get_invoice_file_url(self, obj):
        request = self.context.get('request')
        if obj.invoice_file and hasattr(obj.invoice_file, 'url'):
            if request:
                return request.build_absolute_uri(obj.invoice_file.url)
            return obj.invoice_file.url
        return None
