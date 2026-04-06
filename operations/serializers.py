from decimal import Decimal

from rest_framework import serializers

from accounts.models import DriverProfile
from operations.models import DriverBalanceTransaction, Notification, PushDevice


class DriverBalanceTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverBalanceTransaction
        fields = '__all__'


class DriverTopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AdminDriverBalanceAdjustSerializer(serializers.Serializer):
    driver_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate_driver_id(self, value):
        if not DriverProfile.objects.filter(pk=value).exists():
            raise serializers.ValidationError('Driver profile does not exist.')
        return value

    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError('Amount cannot be zero.')
        return value


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


class PushDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = '__all__'
        read_only_fields = ['user', 'is_active', 'last_seen_at', 'created_at', 'updated_at']


class PushDeviceRegisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096)
    platform = serializers.ChoiceField(choices=[choice for choice, _ in PushDevice.Platform.choices])


class PushDeviceUnregisterSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=4096)


class PushSendSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    body = serializers.CharField(max_length=5000)
    user_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=['admin', 'pharmacy', 'driver', 'customer']),
        required=False,
        allow_empty=True,
    )
    data = serializers.DictField(required=False, default=dict)


class DistanceEstimateRequestSerializer(serializers.Serializer):
    origin_lat = serializers.FloatField()
    origin_lng = serializers.FloatField()
    destination_lat = serializers.FloatField()
    destination_lng = serializers.FloatField()
    pricing_reference_mode = serializers.ChoiceField(
        choices=['pharmacy_to_customer', 'city_center_to_customer'],
        required=False,
    )


class DistanceEstimateResponseSerializer(serializers.Serializer):
    distance_km = serializers.FloatField()
    duration_seconds = serializers.IntegerField()
    distance_text = serializers.CharField()
    duration_text = serializers.CharField()
    zone_id = serializers.UUIDField(allow_null=True)
    zone_name = serializers.CharField(allow_blank=True)
    base_delivery_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
