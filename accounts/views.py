from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomerProfile, DriverProfile, User
from accounts.serializers import CustomerProfileSerializer, DriverProfileSerializer, UserSerializer


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
