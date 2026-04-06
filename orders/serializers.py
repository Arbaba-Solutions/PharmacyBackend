from rest_framework import serializers

from orders.models import BlacklistLog, Dispute, Order, OrderItem, Prescription
from orders.pricing import calculate_order_pricing, quantize_money


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'inventory_item', 'drug_name', 'quantity', 'unit_price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)
    pharmacy_latitude = serializers.SerializerMethodField()
    pharmacy_longitude = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = '__all__'

    def get_pharmacy_latitude(self, obj):
        return obj.pharmacy.latitude if obj.pharmacy else None

    def get_pharmacy_longitude(self, obj):
        return obj.pharmacy.longitude if obj.pharmacy else None

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        zone = validated_data['delivery_zone']
        is_customer_urgent = validated_data.get('is_customer_urgent', False)
        pricing = calculate_order_pricing(zone=zone, is_customer_urgent=is_customer_urgent)

        validated_data['priority'] = Order.Priority.URGENT if is_customer_urgent else Order.Priority.NORMAL
        validated_data['delivery_price'] = pricing['delivery_price']
        validated_data['platform_fee'] = pricing['platform_fee']
        validated_data['applied_surge_multiplier'] = pricing['applied_surge_multiplier']
        validated_data['is_zone_surge_active'] = pricing['is_zone_surge_active']

        order = Order.objects.create(**validated_data)
        running_total = 0
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
            running_total += item['quantity'] * item['unit_price']

        order.drug_cost_total = quantize_money(running_total)
        order.save(update_fields=['drug_cost_total', 'updated_at'])
        return order


class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prescription
        fields = '__all__'
        read_only_fields = ['approved_by_user', 'approved_at', 'rejected_by_user', 'rejected_at']


class BlacklistLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlacklistLog
        fields = '__all__'


class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = '__all__'


class PricingPreviewRequestSerializer(serializers.Serializer):
    delivery_zone_id = serializers.UUIDField()
    is_customer_urgent = serializers.BooleanField(default=False)


class PricingPreviewResponseSerializer(serializers.Serializer):
    delivery_zone_id = serializers.UUIDField()
    delivery_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    applied_surge_multiplier = serializers.DecimalField(max_digits=4, decimal_places=2)
    is_zone_surge_active = serializers.BooleanField()
