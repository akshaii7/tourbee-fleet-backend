import uuid
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
            'emergency_contact_phone', 'joining_date', 'notes', 'created_at', 'updated_at'
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
    # For creating driver along with a user account
    username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'driver_type', 'license_number', 'license_expiry',
            'daily_rent_amount', 'assigned_vehicle', 'is_active',
            'emergency_contact_name', 'emergency_contact_phone',
            'joining_date', 'notes',
            'username', 'email', 'first_name', 'last_name', 'password', 'phone_number'
        ]
        extra_kwargs = {
            'user': {'required': False},
            'license_number': {'required': False, 'allow_blank': True},
            'license_expiry': {'required': False, 'allow_null': True},
            'emergency_contact_name': {'required': False, 'allow_null': True, 'allow_blank': True},
            'emergency_contact_phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'daily_rent_amount': {'required': False},
            'assigned_vehicle': {'required': False, 'allow_null': True},
        }

    def _get_unique_license(self, username=None):
        """Generate a unique placeholder license number if not provided."""
        prefix = (username or 'DRV').upper()[:4].replace(' ', '')
        candidate = f"TMP-{prefix}-{uuid.uuid4().hex[:6].upper()}"
        # Ensure uniqueness in case of collision
        while Driver.objects.filter(license_number=candidate).exists():
            candidate = f"TMP-{prefix}-{uuid.uuid4().hex[:6].upper()}"
        return candidate

    def create(self, validated_data):
        username = validated_data.pop('username', None)
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', '')
        last_name = validated_data.pop('last_name', '')
        password = validated_data.pop('password', 'Driver@2026')
        phone_number = validated_data.pop('phone_number', '')

        if 'user' not in validated_data and username:
            # Auto-generate email if not provided
            safe_email = email.strip() if email and email.strip() else f"{username.replace(' ', '_')}_{uuid.uuid4().hex[:6]}@tourbee.in"
            user = User.objects.create_user(
                username=username,
                email=safe_email,
                first_name=first_name or '',
                last_name=last_name or '',
                role=User.Role.DRIVER,
                phone_number=phone_number or None
            )
            user.set_password(password or 'Driver@2026')
            user.save()
            validated_data['user'] = user

        # Auto-generate license_number if missing or blank
        license_num = validated_data.get('license_number', '')
        if not license_num or not str(license_num).strip():
            validated_data['license_number'] = self._get_unique_license(username)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        password = validated_data.pop('password', None)
        phone_number = validated_data.pop('phone_number', None)
        validated_data.pop('username', None)

        # If license_number is blank/empty in update, keep existing
        if 'license_number' in validated_data:
            if not validated_data['license_number'] or not str(validated_data['license_number']).strip():
                validated_data['license_number'] = instance.license_number

        user = instance.user
        if user:
            user_updated = False
            if first_name is not None and first_name != '':
                user.first_name = first_name
                user_updated = True
            if last_name is not None:
                user.last_name = last_name
                user_updated = True
            if email is not None and email.strip() != '':
                user.email = email.strip()
                user_updated = True
            if phone_number is not None and phone_number.strip() != '':
                user.phone_number = phone_number.strip()
                user_updated = True
            if password and password.strip():
                user.set_password(password)
                user_updated = True
            if 'is_active' in validated_data:
                user.is_active = validated_data['is_active']
                user_updated = True
            if user_updated:
                user.save()

        return super().update(instance, validated_data)
