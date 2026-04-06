from rest_framework import serializers

from orders.models import BlacklistLog, Dispute, Order, OrderItem, Prescription


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
        order = Order.objects.create(**validated_data)
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
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
