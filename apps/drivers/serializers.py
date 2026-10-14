from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Driver
from apps.vehicles.serializers import VehicleSerializer

User = get_user_model()

class DriverSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    
    assigned_vehicle_reg = serializers.SerializerMethodField()
    assigned_vehicle_name = serializers.SerializerMethodField()

    class Meta:
        model = Driver
        fields = [
            'id', 'user_id', 'username', 'full_name', 'first_name', 'last_name', 'email', 'phone_number',
            'driver_type', 'license_number', 'license_expiry',
            'daily_rent_amount', 'assigned_vehicle', 'assigned_vehicle_reg',
            'assigned_vehicle_name', 'is_active', 'emergency_contact_name',
            'emergency_contact_phone', 'bank_account_number', 'bank_ifsc_code',
            'upi_id', 'joining_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_assigned_vehicle_reg(self, obj):
        if obj.assigned_vehicle:
            return obj.assigned_vehicle.registration_number
        return None

    def get_assigned_vehicle_name(self, obj):
        if obj.assigned_vehicle:
            return f"{obj.assigned_vehicle.make} {obj.assigned_vehicle.model}"
        return None

class DriverCreateUpdateSerializer(serializers.ModelSerializer):
    # For creating driver along with a user account if desired
    username = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    first_name = serializers.CharField(write_only=True, required=False)
    last_name = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False)
    phone_number = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'driver_type', 'license_number', 'license_expiry',
            'daily_rent_amount', 'assigned_vehicle', 'is_active',
            'emergency_contact_name', 'emergency_contact_phone',
            'bank_account_number', 'bank_ifsc_code', 'upi_id',
            'joining_date', 'notes',
            'username', 'email', 'first_name', 'last_name', 'password', 'phone_number'
        ]
        extra_kwargs = {
            'user': {'required': False}
        }

    def create(self, validated_data):
        username = validated_data.pop('username', None)
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        password = validated_data.pop('password', 'Driver@2026')
        phone_number = validated_data.pop('phone_number', '')

        if 'user' not in validated_data and username:
            user = User.objects.create_user(
                username=username,
                email=email or f"{username}@tourbee.in",
                first_name=first_name,
                last_name=last_name,
                role=User.Role.DRIVER,
                phone_number=phone_number
            )
            user.set_password(password)
            user.save()
            validated_data['user'] = user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        password = validated_data.pop('password', None)
        phone_number = validated_data.pop('phone_number', None)
        validated_data.pop('username', None)

        user = instance.user
        if user:
            user_updated = False
            if first_name is not None:
                user.first_name = first_name
                user_updated = True
            if last_name is not None:
                user.last_name = last_name
                user_updated = True
            if email is not None and email != '':
                user.email = email
                user_updated = True
            if phone_number is not None:
                user.phone_number = phone_number
                user_updated = True
            if password:
                user.set_password(password)
                user_updated = True
            if 'is_active' in validated_data:
                user.is_active = validated_data['is_active']
                user_updated = True
            if user_updated:
                user.save()

        return super().update(instance, validated_data)

