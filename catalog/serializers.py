from rest_framework import serializers

from catalog.models import DeliveryZone, Pharmacy, PharmacyInventory


class PharmacySerializer(serializers.ModelSerializer):
    class Meta:
        model = Pharmacy
        fields = '__all__'


class PharmacyInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmacyInventory
        fields = '__all__'


class DeliveryZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryZone
        fields = '__all__'
