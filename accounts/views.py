from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomerProfile, DriverProfile, User
from accounts.serializers import (
	AdminCustomerSerializer,
	AdminCustomerUnblacklistSerializer,
	CustomerProfileSerializer,
	DriverProfileSerializer,
	UserSerializer,
)
from operations.fcm import send_push_to_user_ids
from pharmacies_backend.permissions import IsAdmin


class MeView(APIView):
	def get(self, request):
		return Response(UserSerializer(request.user).data)


class MyCustomerProfileView(generics.RetrieveUpdateAPIView):
	serializer_class = CustomerProfileSerializer

	def get_object(self):
		if self.request.user.role != User.Role.CUSTOMER:
			raise PermissionDenied('Only customer accounts can access this endpoint.')
		profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
		return profile


class MyDriverProfileView(generics.RetrieveUpdateAPIView):
	serializer_class = DriverProfileSerializer

	def get_object(self):
		if self.request.user.role != User.Role.DRIVER:
			raise PermissionDenied('Only driver accounts can access this endpoint.')
		profile, _ = DriverProfile.objects.get_or_create(user=self.request.user)
		return profile


class AdminCustomerListView(generics.ListAPIView):
	permission_classes = [IsAdmin]
	serializer_class = AdminCustomerSerializer
	queryset = CustomerProfile.objects.select_related('user').order_by('-created_at')


class AdminCustomerUnblacklistView(APIView):
	permission_classes = [IsAdmin]

	def post(self, request, pk):
		serializer = AdminCustomerUnblacklistSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		payload = serializer.validated_data

		customer = CustomerProfile.objects.select_related('user').get(pk=pk)
		customer.user.is_blacklisted = False
		customer.user.save(update_fields=['is_blacklisted', 'updated_at'])
		customer.blacklisted_at = None
		customer.blacklisted_by = None
		if payload['reset_flags']:
			customer.flag_count = 0
		customer.save(update_fields=['blacklisted_at', 'blacklisted_by', 'flag_count', 'updated_at'])

		send_push_to_user_ids(
			user_ids=[str(customer.user_id)],
			title='Blacklist lifted',
			body='Your account restrictions were lifted by an admin review.',
			data={'event': 'customer_unblacklisted', 'customer_id': str(customer.id), 'at': timezone.now().isoformat()},
		)

		return Response(AdminCustomerSerializer(customer).data)
