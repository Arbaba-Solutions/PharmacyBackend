from rest_framework import generics

from operations.models import DriverBalanceTransaction, Notification
from operations.serializers import DriverBalanceTransactionSerializer, NotificationSerializer
from pharmacies_backend.permissions import IsAdmin


class DriverBalanceTransactionListView(generics.ListAPIView):
	serializer_class = DriverBalanceTransactionSerializer

	def get_queryset(self):
		user = self.request.user
		if user.role == 'admin':
			return DriverBalanceTransaction.objects.all().order_by('-created_at')
		if user.role == 'driver':
			return DriverBalanceTransaction.objects.filter(driver__user=user).order_by('-created_at')
		return DriverBalanceTransaction.objects.none()


class NotificationListView(generics.ListAPIView):
	serializer_class = NotificationSerializer

	def get_queryset(self):
		user = self.request.user
		if user.role == 'admin':
			return Notification.objects.all().order_by('-created_at')
		return Notification.objects.filter(user=user).order_by('-created_at')


class NotificationCreateView(generics.CreateAPIView):
	serializer_class = NotificationSerializer
	permission_classes = [IsAdmin]
