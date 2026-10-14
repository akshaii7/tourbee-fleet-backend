from rest_framework import serializers
from .models import Vehicle

class VehicleSerializer(serializers.ModelSerializer):
    assigned_driver_name = serializers.SerializerMethodField()
    assigned_driver_id = serializers.SerializerMethodField()
    insurance_status = serializers.ReadOnlyField()
    fitness_status = serializers.ReadOnlyField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'registration_number', 'make', 'model', 'year',
            'fuel_type', 'status', 'rc_number', 'insurance_policy_no',
            'insurance_expiry', 'fitness_expiry', 'pollution_expiry',
            'current_odometer', 'daily_rent_rate', 'notes',
            'assigned_driver_name', 'assigned_driver_id',
            'insurance_status', 'fitness_status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_assigned_driver_name(self, obj):
        if hasattr(obj, 'assigned_driver'):
            return obj.assigned_driver.user.get_full_name() or obj.assigned_driver.user.username
        return None

    def get_assigned_driver_id(self, obj):
        if hasattr(obj, 'assigned_driver'):
            return obj.assigned_driver.id
        return None
