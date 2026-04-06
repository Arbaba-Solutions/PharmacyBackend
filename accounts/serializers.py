from rest_framework import serializers

from accounts.models import CustomerProfile, DriverProfile, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'role',
            'email',
            'phone',
            'full_name',
            'is_active',
            'is_blacklisted',
            'created_at',
            'updated_at',
        ]


class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = '__all__'


class DriverProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = '__all__'


class AdminCustomerSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    is_blacklisted = serializers.BooleanField(source='user.is_blacklisted', read_only=True)

    class Meta:
        model = CustomerProfile
        fields = [
            'id',
            'user_id',
            'full_name',
            'email',
            'phone',
            'flag_count',
            'is_blacklisted',
            'blacklisted_at',
            'default_address',
            'created_at',
            'updated_at',
        ]


class AdminCustomerUnblacklistSerializer(serializers.Serializer):
    reset_flags = serializers.BooleanField(required=False, default=False)
