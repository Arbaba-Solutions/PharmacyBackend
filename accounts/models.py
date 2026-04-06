import uuid

from django.db import models


class TimeStampedModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class User(TimeStampedModel):
	class Role(models.TextChoices):
		ADMIN = 'admin', 'Admin'
		PHARMACY = 'pharmacy', 'Pharmacy'
		DRIVER = 'driver', 'Driver'
		CUSTOMER = 'customer', 'Customer'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	role = models.CharField(max_length=20, choices=Role.choices)
	email = models.EmailField(blank=True)
	phone = models.CharField(max_length=32, blank=True)
	full_name = models.CharField(max_length=255, blank=True)
	is_active = models.BooleanField(default=True)
	is_blacklisted = models.BooleanField(default=False)

	class Meta:
		db_table = 'users'
		indexes = [models.Index(fields=['role'])]

	@property
	def is_authenticated(self):
		return True

	@property
	def is_anonymous(self):
		return False

	def __str__(self):
		return f'{self.full_name or self.email or self.id} ({self.role})'


class CustomerProfile(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
	default_address = models.TextField(blank=True)
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	flag_count = models.PositiveIntegerField(default=0)
	blacklisted_at = models.DateTimeField(null=True, blank=True)
	blacklisted_by = models.ForeignKey(
		User,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='customer_blacklist_actions',
	)

	class Meta:
		db_table = 'customers'


class DriverProfile(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
	is_approved = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	vehicle_type = models.CharField(max_length=80, blank=True)
	last_latitude = models.FloatField(null=True, blank=True)
	last_longitude = models.FloatField(null=True, blank=True)
	last_location_at = models.DateTimeField(null=True, blank=True)

	class Meta:
		db_table = 'drivers'


class AuthAuditLog(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_audit_logs')
	event = models.CharField(max_length=120)
	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		db_table = 'auth_audit_log'
