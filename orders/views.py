from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import BlacklistLog, Dispute, Order, Prescription
from orders.serializers import (
	BlacklistLogSerializer,
	DisputeSerializer,
	OrderSerializer,
	PrescriptionSerializer,
)
from pharmacies_backend.permissions import IsAdmin, IsAdminOrPharmacy


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
		if user.role == 'customer':
			try:
				customer_profile = user.customer_profile
			except Exception as exc:  # noqa: BLE001
				raise ValidationError('Customer profile is required before placing orders.') from exc
			serializer.save(customer=customer_profile)
			return
		serializer.save()


class OrderDetailView(generics.RetrieveUpdateAPIView):
	queryset = Order.objects.all()
	serializer_class = OrderSerializer


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
