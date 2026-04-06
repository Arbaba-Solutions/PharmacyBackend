from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DriverProfile, User
from catalog.models import DeliveryZone
from operations.fcm import send_push_to_user_ids
from orders.models import BlacklistLog, Dispute, Order, Prescription
from orders.pricing import calculate_order_pricing
from orders.serializers import (
	BlacklistLogSerializer,
	DisputeSerializer,
	OrderSerializer,
	PricingPreviewRequestSerializer,
	PricingPreviewResponseSerializer,
	PrescriptionSerializer,
)
from pharmacies_backend.permissions import IsAdmin, IsAdminOrPharmacy, IsDriver


class OrderListCreateView(generics.ListCreateAPIView):
	serializer_class = OrderSerializer

	def get_queryset(self):
		user = self.request.user
		if user.role == 'admin':
			return Order.objects.all().order_by('-created_at')
		if user.role == 'customer':
			return Order.objects.filter(customer__user=user).order_by('-created_at')
		if user.role == 'driver':
			return Order.objects.filter(driver__user=user).order_by('-created_at')
		if user.role == 'pharmacy':
			return Order.objects.filter(pharmacy__user=user).order_by('-created_at')
		return Order.objects.none()

	def perform_create(self, serializer):
		user = self.request.user
		if user.role not in {'admin', 'customer'}:
			raise PermissionDenied('Only customers or admins can create orders.')

		order = None
		if user.role == 'customer':
			try:
				customer_profile = user.customer_profile
			except Exception as exc:  # noqa: BLE001
				raise ValidationError('Customer profile is required before placing orders.') from exc
			order = serializer.save(customer=customer_profile)
		else:
			order = serializer.save()

		admin_user_ids = [str(pk) for pk in User.objects.filter(role='admin', is_active=True).values_list('id', flat=True)]
		if admin_user_ids:
			send_push_to_user_ids(
				user_ids=admin_user_ids,
				title='New prescription pending approval',
				body='A customer order was placed and is waiting for prescription approval.',
				data={'event': 'prescription_pending', 'order_id': str(order.id)},
				order=order,
			)

		if order.pharmacy and order.pharmacy.user_id:
			send_push_to_user_ids(
				user_ids=[str(order.pharmacy.user_id)],
				title='New prescription pending your approval',
				body='A new order requires pharmacy prescription review.',
				data={'event': 'pharmacy_prescription_pending', 'order_id': str(order.id)},
				order=order,
			)

		send_push_to_user_ids(
			user_ids=[str(order.customer.user_id)],
			title='Order received and pending prescription approval',
			body='Your order is created and waiting for prescription approval.',
			data={'event': 'customer_order_received', 'order_id': str(order.id)},
			order=order,
		)


class OrderDetailView(generics.RetrieveUpdateAPIView):
	queryset = Order.objects.all()
	serializer_class = OrderSerializer


class OrderPricingPreviewView(APIView):
	def post(self, request):
		serializer = PricingPreviewRequestSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		payload = serializer.validated_data

		zone = DeliveryZone.objects.get(pk=payload['delivery_zone_id'])
		pricing = calculate_order_pricing(zone=zone, is_customer_urgent=payload['is_customer_urgent'])

		response_payload = {
			'delivery_zone_id': zone.id,
			**pricing,
		}
		response_serializer = PricingPreviewResponseSerializer(data=response_payload)
		response_serializer.is_valid(raise_exception=True)
		return Response(response_serializer.validated_data)


class PrescriptionQueueView(generics.ListAPIView):
	serializer_class = PrescriptionSerializer
	permission_classes = [IsAdminOrPharmacy]

	def get_queryset(self):
		user = self.request.user
		queryset = Prescription.objects.filter(status=Prescription.Status.PENDING).order_by('created_at')
		if user.role == 'pharmacy':
			queryset = queryset.filter(order__pharmacy__user=user)
		return queryset


class PrescriptionApproveView(APIView):
	permission_classes = [IsAdminOrPharmacy]

	@transaction.atomic
	def post(self, request, pk):
		prescription = Prescription.objects.select_for_update().select_related('order').get(pk=pk)
		if prescription.status != Prescription.Status.PENDING:
			return Response(
				{'detail': 'Prescription already processed.'},
				status=status.HTTP_409_CONFLICT,
			)

		if request.user.role == 'pharmacy' and (
			not prescription.order.pharmacy or prescription.order.pharmacy.user_id != request.user.id
		):
			raise PermissionDenied('You can only approve prescriptions for your pharmacy orders.')

		prescription.status = Prescription.Status.APPROVED
		prescription.approved_by_type = 'admin' if request.user.role == 'admin' else 'pharmacy'
		prescription.approved_by_user = request.user
		prescription.approved_at = timezone.now()
		prescription.rejected_by_user = None
		prescription.rejected_at = None
		prescription.rejection_reason = ''
		prescription.save(update_fields=[
			'status',
			'approved_by_type',
			'approved_by_user',
			'approved_at',
			'rejected_by_user',
			'rejected_at',
			'rejection_reason',
			'updated_at',
		])

		order = prescription.order
		if order.status == Order.Status.PENDING_PRESCRIPTION:
			order.status = Order.Status.APPROVED_PENDING_DRIVER
			order.save(update_fields=['status', 'updated_at'])

		send_push_to_user_ids(
			user_ids=[str(order.customer.user_id)],
			title='Prescription approved, driver being assigned',
			body='Your prescription is approved and the order is now visible to nearby drivers.',
			data={'event': 'prescription_approved', 'order_id': str(order.id)},
			order=order,
		)

		if request.user.role == 'admin' and order.pharmacy and order.pharmacy.user_id:
			send_push_to_user_ids(
				user_ids=[str(order.pharmacy.user_id)],
				title='Prescription already approved by admin',
				body='No pharmacy action is needed for this prescription.',
				data={'event': 'prescription_approved_by_admin', 'order_id': str(order.id)},
				order=order,
			)
		if request.user.role == 'pharmacy':
			admin_user_ids = [
				str(pk) for pk in User.objects.filter(role='admin', is_active=True).values_list('id', flat=True)
			]
			if admin_user_ids:
				send_push_to_user_ids(
					user_ids=admin_user_ids,
					title='Prescription already approved by pharmacy',
					body='The pharmacy approved this prescription first.',
					data={'event': 'prescription_approved_by_pharmacy', 'order_id': str(order.id)},
					order=order,
				)

		driver_user_ids = [
			str(user_id)
			for user_id in DriverProfile.objects.filter(is_active=True, is_approved=True).values_list('user_id', flat=True)
		]
		if driver_user_ids:
			is_urgent = order.priority == 'urgent'
			send_push_to_user_ids(
				user_ids=driver_user_ids,
				title='New order available nearby',
				body='Urgent order is available now.' if is_urgent else 'A new order is available for pickup.',
				data={
					'event': 'driver_new_order',
					'order_id': str(order.id),
					'urgent': 'true' if is_urgent else 'false',
					'sound': 'urgent_alert' if is_urgent else 'default',
				},
				order=order,
			)

		return Response(PrescriptionSerializer(prescription).data)


class PrescriptionRejectView(APIView):
	permission_classes = [IsAdminOrPharmacy]

	@transaction.atomic
	def post(self, request, pk):
		reason = request.data.get('reason', '').strip()
		if not reason:
			raise ValidationError({'reason': 'Reason is required.'})

		prescription = Prescription.objects.select_for_update().select_related('order').get(pk=pk)
		if prescription.status != Prescription.Status.PENDING:
			return Response(
				{'detail': 'Prescription already processed.'},
				status=status.HTTP_409_CONFLICT,
			)

		if request.user.role == 'pharmacy' and (
			not prescription.order.pharmacy or prescription.order.pharmacy.user_id != request.user.id
		):
			raise PermissionDenied('You can only reject prescriptions for your pharmacy orders.')

		prescription.status = Prescription.Status.REJECTED
		prescription.rejected_by_user = request.user
		prescription.rejected_at = timezone.now()
		prescription.rejection_reason = reason
		prescription.approved_by_type = ''
		prescription.approved_by_user = None
		prescription.approved_at = None
		prescription.save(update_fields=[
			'status',
			'rejected_by_user',
			'rejected_at',
			'rejection_reason',
			'approved_by_type',
			'approved_by_user',
			'approved_at',
			'updated_at',
		])

		return Response(PrescriptionSerializer(prescription).data)


class DisputeListCreateView(generics.ListCreateAPIView):
	serializer_class = DisputeSerializer

	def get_queryset(self):
		user = self.request.user
		if user.role == 'admin':
			return Dispute.objects.all().order_by('-created_at')
		if user.role == 'customer':
			return Dispute.objects.filter(customer__user=user).order_by('-created_at')
		if user.role == 'driver':
			return Dispute.objects.filter(driver__user=user).order_by('-created_at')
		return Dispute.objects.none()


class BlacklistLogListView(generics.ListAPIView):
	serializer_class = BlacklistLogSerializer
	queryset = BlacklistLog.objects.all().order_by('-created_at')
	permission_classes = [IsAdmin]


class DriverAcceptOrderView(APIView):
	permission_classes = [IsDriver]

	@transaction.atomic
	def post(self, request, pk):
		order = Order.objects.select_for_update().select_related('customer').get(pk=pk)
		if order.status != Order.Status.APPROVED_PENDING_DRIVER:
			return Response({'detail': 'Order is not available for acceptance.'}, status=status.HTTP_409_CONFLICT)

		driver = DriverProfile.objects.select_for_update().get(user=request.user)
		if not driver.is_approved:
			return Response({'detail': 'Driver is pending admin approval.'}, status=status.HTTP_403_FORBIDDEN)
		if driver.current_balance < order.platform_fee:
			return Response({'detail': 'Insufficient balance for platform fee.'}, status=status.HTTP_403_FORBIDDEN)

		order.driver = driver
		order.status = Order.Status.DRIVER_ASSIGNED
		order.accepted_at = timezone.now()
		order.save(update_fields=['driver', 'status', 'accepted_at', 'updated_at'])

		send_push_to_user_ids(
			user_ids=[str(order.customer.user_id)],
			title='Driver accepted your order',
			body='A driver accepted your order and is preparing for pickup.',
			data={'event': 'customer_driver_accepted', 'order_id': str(order.id)},
			order=order,
		)

		other_driver_user_ids = [
			str(user_id)
			for user_id in DriverProfile.objects.filter(is_active=True, is_approved=True)
			.exclude(user_id=request.user.id)
			.values_list('user_id', flat=True)
		]
		if other_driver_user_ids:
			send_push_to_user_ids(
				user_ids=other_driver_user_ids,
				title='Order taken by another driver',
				body='This order is no longer available in your feed.',
				data={'event': 'driver_order_taken', 'order_id': str(order.id)},
				order=order,
			)

		return Response(OrderSerializer(order).data)


class DriverMarkPurchasedView(APIView):
	permission_classes = [IsDriver]

	def post(self, request, pk):
		order = Order.objects.select_related('driver', 'customer').get(pk=pk)
		if not order.driver or order.driver.user_id != request.user.id:
			raise PermissionDenied('You can only update your own assigned order.')

		order.status = Order.Status.DRUG_PURCHASED
		order.purchased_at = timezone.now()
		order.save(update_fields=['status', 'purchased_at', 'updated_at'])

		send_push_to_user_ids(
			user_ids=[str(order.customer.user_id)],
			title='Driver is on the way',
			body='Your driver purchased the drug and is heading to your address.',
			data={'event': 'customer_driver_on_the_way', 'order_id': str(order.id)},
			order=order,
		)

		return Response(OrderSerializer(order).data)


class DriverMarkDeliveredView(APIView):
	permission_classes = [IsDriver]

	def post(self, request, pk):
		order = Order.objects.select_related('driver', 'customer').get(pk=pk)
		if not order.driver or order.driver.user_id != request.user.id:
			raise PermissionDenied('You can only update your own assigned order.')

		order.status = Order.Status.DELIVERED
		order.delivered_at = timezone.now()
		order.save(update_fields=['status', 'delivered_at', 'updated_at'])

		send_push_to_user_ids(
			user_ids=[str(order.customer.user_id)],
			title='Order delivered',
			body='Your order has been marked delivered.',
			data={'event': 'customer_order_delivered', 'order_id': str(order.id)},
			order=order,
		)

		return Response(OrderSerializer(order).data)
