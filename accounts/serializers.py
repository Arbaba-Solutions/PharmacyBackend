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
