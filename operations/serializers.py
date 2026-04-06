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
