import uuid

from django.db import models

from accounts.models import DriverProfile, TimeStampedModel, User


class DriverBalanceTransaction(models.Model):
	class TransactionType(models.TextChoices):
		TOP_UP = 'top_up', 'Top Up'
		DELIVERY_FEE_DEDUCTION = 'delivery_fee_deduction', 'Delivery Fee Deduction'
		MANUAL_ADJUSTMENT = 'manual_adjustment', 'Manual Adjustment'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	driver = models.ForeignKey(DriverProfile, on_delete=models.PROTECT, related_name='balance_transactions')
	order = models.ForeignKey(
		'orders.Order',
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='balance_transactions',
	)
	transaction_type = models.CharField(max_length=32, choices=TransactionType.choices)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	balance_before = models.DecimalField(max_digits=12, decimal_places=2)
	balance_after = models.DecimalField(max_digits=12, decimal_places=2)
	initiated_by_user = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='initiated_balance_transactions',
	)
	note = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		db_table = 'driver_balance_transactions'
		indexes = [models.Index(fields=['driver', '-created_at'])]


class Notification(TimeStampedModel):
	class Channel(models.TextChoices):
		PUSH = 'push', 'Push'
		IN_APP = 'in_app', 'In-App'
		EMAIL = 'email', 'Email'
		SMS = 'sms', 'SMS'

	class DeliveryState(models.TextChoices):
		QUEUED = 'queued', 'Queued'
		SENT = 'sent', 'Sent'
		FAILED = 'failed', 'Failed'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
	order = models.ForeignKey(
		'orders.Order',
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='notifications',
	)
	title = models.CharField(max_length=255)
	body = models.TextField()
	channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.PUSH)
	delivery_state = models.CharField(max_length=20, choices=DeliveryState.choices, default=DeliveryState.QUEUED)
	retry_count = models.PositiveIntegerField(default=0)
	last_attempt_at = models.DateTimeField(null=True, blank=True)
	sent_at = models.DateTimeField(null=True, blank=True)
	failure_reason = models.TextField(blank=True)
	payload = models.JSONField(default=dict, blank=True)

	class Meta:
		db_table = 'notifications'
		indexes = [models.Index(fields=['user', 'delivery_state'])]


class PushDevice(TimeStampedModel):
	class Platform(models.TextChoices):
		ANDROID = 'android', 'Android'
		IOS = 'ios', 'iOS'
		WEB = 'web', 'Web'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_devices')
	token = models.TextField(unique=True)
	platform = models.CharField(max_length=20, choices=Platform.choices)
	is_active = models.BooleanField(default=True)
	last_seen_at = models.DateTimeField(auto_now=True)

	class Meta:
		db_table = 'push_devices'
		indexes = [models.Index(fields=['user', 'platform', 'is_active'])]
