from decimal import Decimal

from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DriverProfile, User
from operations.fcm import send_push_to_user_ids
from operations.google_maps import GoogleDistanceMatrixError, get_distance_matrix_km, resolve_delivery_zone
from operations.models import DriverBalanceTransaction, Notification, PushDevice
from operations.serializers import (
	AdminDriverBalanceAdjustSerializer,
	DistanceEstimateRequestSerializer,
	DistanceEstimateResponseSerializer,
	DriverBalanceTransactionSerializer,
	DriverTopUpSerializer,
	NotificationSerializer,
	PushDeviceRegisterSerializer,
	PushDeviceSerializer,
	PushDeviceUnregisterSerializer,
	PushSendSerializer,
)
from pharmacies_backend.permissions import IsAdmin, IsDriver


def _apply_balance_change(
	*,
	driver: DriverProfile,
	amount: Decimal,
	transaction_type: str,
	initiated_by_user,
	order=None,
	note: str = '',
):
	balance_before = driver.current_balance
	balance_after = balance_before + amount
	if balance_after < Decimal('0.00'):
		raise ValidationError({'detail': 'Insufficient driver balance for this operation.'})

	driver.current_balance = balance_after
	driver.save(update_fields=['current_balance', 'updated_at'])
	transaction = DriverBalanceTransaction.objects.create(
		driver=driver,
		order=order,
		transaction_type=transaction_type,
		amount=amount,
		balance_before=balance_before,
		balance_after=balance_after,
		initiated_by_user=initiated_by_user,
		note=note,
	)
	return transaction


class DriverBalanceTransactionListView(generics.ListAPIView):
	serializer_class = DriverBalanceTransactionSerializer

	def get_queryset(self):
		user = self.request.user
		if user.role == 'admin':
			return DriverBalanceTransaction.objects.all().order_by('-created_at')
		if user.role == 'driver':
			return DriverBalanceTransaction.objects.filter(driver__user=user).order_by('-created_at')
		return DriverBalanceTransaction.objects.none()


class DriverTopUpView(APIView):
	permission_classes = [IsDriver]

	@transaction.atomic
	def post(self, request):
		serializer = DriverTopUpSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		payload = serializer.validated_data

		driver = DriverProfile.objects.select_for_update().get(user=request.user)
		transaction_row = _apply_balance_change(
			driver=driver,
			amount=payload['amount'],
			transaction_type=DriverBalanceTransaction.TransactionType.TOP_UP,
			initiated_by_user=request.user,
			note=payload.get('note', '').strip() or 'Driver top-up via mobile app',
		)

		return Response(DriverBalanceTransactionSerializer(transaction_row).data, status=status.HTTP_201_CREATED)


class AdminDriverBalanceAdjustView(APIView):
	permission_classes = [IsAdmin]

	@transaction.atomic
	def post(self, request):
		serializer = AdminDriverBalanceAdjustSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		payload = serializer.validated_data

		driver = DriverProfile.objects.select_for_update().get(pk=payload['driver_id'])
		transaction_row = _apply_balance_change(
			driver=driver,
			amount=payload['amount'],
			transaction_type=DriverBalanceTransaction.TransactionType.MANUAL_ADJUSTMENT,
			initiated_by_user=request.user,
			note=payload.get('note', '').strip() or 'Admin manual balance adjustment',
		)

		return Response(DriverBalanceTransactionSerializer(transaction_row).data, status=status.HTTP_201_CREATED)


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
