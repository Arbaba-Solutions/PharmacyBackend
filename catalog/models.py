import uuid

from django.db import models

from accounts.models import TimeStampedModel, User


class Pharmacy(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	user = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='pharmacies',
	)
	name = models.CharField(max_length=255)
	contact_phone = models.CharField(max_length=32, blank=True)
	address = models.TextField()
	latitude = models.FloatField(null=True, blank=True)
	longitude = models.FloatField(null=True, blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		db_table = 'pharmacies'


class PharmacyInventory(TimeStampedModel):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name='inventory_items')
	drug_name = models.CharField(max_length=255)
	description = models.TextField(blank=True)
	unit_price = models.DecimalField(max_digits=12, decimal_places=2)
	is_available = models.BooleanField(default=True)
	last_updated_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='inventory_updates',
	)

	class Meta:
		db_table = 'pharmacy_inventory'
		constraints = [
			models.UniqueConstraint(fields=['pharmacy', 'drug_name'], name='uq_pharmacy_drug_name'),
		]
		indexes = [models.Index(fields=['pharmacy', 'drug_name'])]


class DeliveryZone(TimeStampedModel):
	class PricingReferenceMode(models.TextChoices):
		PHARMACY_TO_CUSTOMER = 'pharmacy_to_customer', 'Pharmacy To Customer'
		CITY_CENTER_TO_CUSTOMER = 'city_center_to_customer', 'City Center To Customer'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	name = models.CharField(max_length=120, unique=True)
	min_radius_km = models.DecimalField(max_digits=8, decimal_places=2)
	max_radius_km = models.DecimalField(max_digits=8, decimal_places=2)
	base_delivery_price = models.DecimalField(max_digits=12, decimal_places=2)
	platform_fee = models.DecimalField(max_digits=12, decimal_places=2)
	surge_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1)
	surge_enabled = models.BooleanField(default=False)
	pricing_reference_mode = models.CharField(
		max_length=32,
		choices=PricingReferenceMode.choices,
		default=PricingReferenceMode.PHARMACY_TO_CUSTOMER,
	)
	city_center_latitude = models.FloatField(null=True, blank=True)
	city_center_longitude = models.FloatField(null=True, blank=True)

	class Meta:
		db_table = 'delivery_zones'
