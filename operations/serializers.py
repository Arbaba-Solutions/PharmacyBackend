from rest_framework import serializers

from operations.models import DriverBalanceTransaction, Notification


class DriverBalanceTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverBalanceTransaction
        fields = '__all__'


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'


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
