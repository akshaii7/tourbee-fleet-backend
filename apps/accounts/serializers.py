from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    driver_profile_id = serializers.SerializerMethodField()
    driver_type = serializers.SerializerMethodField()
    assigned_vehicle = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone_number', 'avatar', 'city', 'state',
            'driver_profile_id', 'driver_type', 'assigned_vehicle',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_driver_profile_id(self, obj):
        if hasattr(obj, 'driver_profile'):
            return obj.driver_profile.id
        return None

    def get_driver_type(self, obj):
        if hasattr(obj, 'driver_profile'):
            return obj.driver_profile.driver_type
        return None

    def get_assigned_vehicle(self, obj):
        if hasattr(obj, 'driver_profile') and obj.driver_profile.assigned_vehicle:
            v = obj.driver_profile.assigned_vehicle
            return {
                'id': v.id,
                'registration_number': v.registration_number,
                'model_name': f"{v.make} {v.model}"
            }
        return None

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name() or user.username,
            'role': user.role,
            'is_admin': user.is_admin,
            'is_driver': user.is_driver,
            'phone_number': user.phone_number,
        }
        if hasattr(user, 'driver_profile'):
            dp = user.driver_profile
            mode = 'REVENUE_SHARING' if dp.driver_type == 'PROFIT_SHARING' else 'FIXED_RENT'
            data['user']['driver_profile'] = {
                'id': dp.id,
                'driver_type': dp.driver_type,
                'payment_mode': mode,
                'daily_rent_amount': str(dp.daily_rent_amount),
                'assigned_vehicle_id': dp.assigned_vehicle_id,
                'assigned_vehicle_reg': dp.assigned_vehicle.registration_number if dp.assigned_vehicle else None,
                'assigned_vehicle_name': f"{dp.assigned_vehicle.make} {dp.assigned_vehicle.model}" if dp.assigned_vehicle else None,
            }
        elif hasattr(user, 'fleet_driver_profile'):
            fp = user.fleet_driver_profile
            dtype = 'PROFIT_SHARING' if fp.payment_mode == 'REVENUE_SHARING' else 'DAILY_RENT'
            data['user']['driver_profile'] = {
                'id': fp.id,
                'driver_type': dtype,
                'payment_mode': fp.payment_mode,
                'daily_rent_amount': '1200.00',
                'assigned_vehicle_id': fp.assigned_vehicle_id,
                'assigned_vehicle_reg': fp.assigned_vehicle.registration_number if fp.assigned_vehicle else None,
                'assigned_vehicle_name': f"{fp.assigned_vehicle.make} {fp.assigned_vehicle.model}" if fp.assigned_vehicle else None,
            }
        else:
            data['user']['driver_profile'] = None

        return data
