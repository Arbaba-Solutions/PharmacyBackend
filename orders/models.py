import uuid

from django.db import models

from accounts.models import CustomerProfile, DriverProfile, TimeStampedModel, User
from catalog.models import DeliveryZone, Pharmacy, PharmacyInventory


class Order(TimeStampedModel):
	class Status(models.TextChoices):
		PENDING_PRESCRIPTION = 'pending_prescription', 'Pending Prescription'
		APPROVED_PENDING_DRIVER = 'approved_pending_driver', 'Approved Pending Driver'
		DRIVER_ASSIGNED = 'driver_assigned', 'Driver Assigned'
		DRUG_PURCHASED = 'drug_purchased', 'Drug Purchased'
		IN_DELIVERY = 'in_delivery', 'In Delivery'
		DELIVERED = 'delivered', 'Delivered'
		CANCELLED = 'cancelled', 'Cancelled'
		DISPUTED = 'disputed', 'Disputed'

	class Priority(models.TextChoices):
		NORMAL = 'normal', 'Normal'
		URGENT = 'urgent', 'Urgent'

	class SourceMode(models.TextChoices):
		CONTRACTED_PHARMACY = 'contracted_pharmacy', 'Contracted Pharmacy'
		EXTERNAL_SOURCING = 'external_sourcing', 'External Sourcing'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name='orders')
	driver = models.ForeignKey(
		DriverProfile,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='orders',
	)
	pharmacy = models.ForeignKey(
		Pharmacy,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='orders',
	)
	delivery_zone = models.ForeignKey(DeliveryZone, on_delete=models.PROTECT, related_name='orders')
	source_mode = models.CharField(max_length=32, choices=SourceMode.choices, default=SourceMode.CONTRACTED_PHARMACY)
	priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
	status = models.CharField(max_length=40, choices=Status.choices, default=Status.PENDING_PRESCRIPTION)
	delivery_address = models.TextField()
	delivery_latitude = models.FloatField(null=True, blank=True)
	delivery_longitude = models.FloatField(null=True, blank=True)
	estimated_distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
	drug_cost_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	delivery_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	applied_surge_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)
	is_customer_urgent = models.BooleanField(default=False)
	is_zone_surge_active = models.BooleanField(default=False)
	accepted_at = models.DateTimeField(null=True, blank=True)
	purchased_at = models.DateTimeField(null=True, blank=True)
	delivered_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		db_table = 'orders'
		indexes = [models.Index(fields=['status', 'priority', '-created_at'])]


class OrderItem(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
	inventory_item = models.ForeignKey(
		PharmacyInventory,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='order_items',
	)
	drug_name = models.CharField(max_length=255)
	quantity = models.PositiveIntegerField()
	unit_price = models.DecimalField(max_digits=12, decimal_places=2)

	class Meta:
		db_table = 'order_items'


class Prescription(TimeStampedModel):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		APPROVED = 'approved', 'Approved'
		REJECTED = 'rejected', 'Rejected'

	class ApproverType(models.TextChoices):
		ADMIN = 'admin', 'Admin'
		PHARMACY = 'pharmacy', 'Pharmacy'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='prescription')
	customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name='prescriptions')
	storage_bucket = models.CharField(max_length=120, default='prescriptions')
	storage_path = models.TextField()
	status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
	approved_by_type = models.CharField(max_length=20, choices=ApproverType.choices, blank=True)
	approved_by_user = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='approved_prescriptions',
	)
	approved_at = models.DateTimeField(null=True, blank=True)
	rejected_by_user = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='rejected_prescriptions',
	)
	rejected_at = models.DateTimeField(null=True, blank=True)
	rejection_reason = models.TextField(blank=True)

	class Meta:
		db_table = 'prescriptions'
		indexes = [models.Index(fields=['status', 'created_at'])]


class BlacklistLog(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='blacklist_logs')
	order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='blacklist_logs')
	reason = models.TextField()
	incident_count_after = models.PositiveIntegerField()
	auto_blacklisted = models.BooleanField(default=False)
	reviewed_by_user = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='reviewed_blacklist_logs',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		db_table = 'blacklist_log'


class Dispute(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='disputes')
	customer = models.ForeignKey(CustomerProfile, on_delete=models.PROTECT, related_name='disputes')
	driver = models.ForeignKey(DriverProfile, on_delete=models.PROTECT, related_name='disputes')
	dispute_type = models.CharField(max_length=120)
	description = models.TextField(blank=True)
	status = models.CharField(max_length=30, default='open')
	created_by_user = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='created_disputes',
	)
	resolved_by_user = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='resolved_disputes',
	)
	resolved_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		db_table = 'disputes'
