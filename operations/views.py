from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from operations.fcm import send_push_to_user_ids
from operations.google_maps import GoogleDistanceMatrixError, get_distance_matrix_km, resolve_delivery_zone
from operations.models import DriverBalanceTransaction, Notification, PushDevice
from operations.serializers import (
	DistanceEstimateRequestSerializer,
	DistanceEstimateResponseSerializer,
	DriverBalanceTransactionSerializer,
	NotificationSerializer,
	PushDeviceRegisterSerializer,
	PushDeviceSerializer,
	PushDeviceUnregisterSerializer,
	PushSendSerializer,
)
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


class PushDeviceRegisterView(APIView):
	def post(self, request):
		serializer = PushDeviceRegisterSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		payload = serializer.validated_data
		device, _ = PushDevice.objects.update_or_create(
			token=payload['token'],
			defaults={
				'user': request.user,
				'platform': payload['platform'],
				'is_active': True,
			},
		)

		return Response(PushDeviceSerializer(device).data, status=status.HTTP_201_CREATED)


class PushDeviceUnregisterView(APIView):
	def post(self, request):
		serializer = PushDeviceUnregisterSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		token = serializer.validated_data['token']

		updated = PushDevice.objects.filter(user=request.user, token=token).update(is_active=False)
		return Response({'unregistered': bool(updated)})


class PushSendView(APIView):
	permission_classes = [IsAdmin]

	def post(self, request):
		serializer = PushSendSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		payload = serializer.validated_data

		queryset = User.objects.filter(is_active=True)
		if payload.get('roles'):
			queryset = queryset.filter(role__in=payload['roles'])
		if payload.get('user_ids'):
			queryset = queryset.filter(id__in=payload['user_ids'])

		user_ids = [str(user_id) for user_id in queryset.values_list('id', flat=True)]
		send_push_to_user_ids(
			user_ids=user_ids,
			title=payload['title'],
			body=payload['body'],
			data=payload.get('data', {}),
		)

		return Response({'sent_to': len(user_ids)})


class DistanceEstimateView(APIView):
	def post(self, request):
		request_serializer = DistanceEstimateRequestSerializer(data=request.data)
		request_serializer.is_valid(raise_exception=True)
		payload = request_serializer.validated_data

		try:
			distance_data = get_distance_matrix_km(
				origin_lat=payload['origin_lat'],
				origin_lng=payload['origin_lng'],
				destination_lat=payload['destination_lat'],
				destination_lng=payload['destination_lng'],
			)
		except GoogleDistanceMatrixError as exc:
			return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
		except Exception as exc:  # noqa: BLE001
			return Response({'detail': f'Distance lookup failed: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)

		zone = resolve_delivery_zone(
			distance_km=distance_data['distance_km'],
			reference_mode=payload.get('pricing_reference_mode'),
		)

		response_payload = {
			**distance_data,
			'zone_id': zone.id if zone else None,
			'zone_name': zone.name if zone else '',
			'base_delivery_price': zone.base_delivery_price if zone else None,
			'platform_fee': zone.platform_fee if zone else None,
		}

		response_serializer = DistanceEstimateResponseSerializer(data=response_payload)
		response_serializer.is_valid(raise_exception=True)
		return Response(response_serializer.validated_data)
