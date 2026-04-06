from rest_framework import generics

from catalog.models import DeliveryZone, Pharmacy, PharmacyInventory
from catalog.serializers import DeliveryZoneSerializer, PharmacyInventorySerializer, PharmacySerializer
from pharmacies_backend.permissions import IsAdmin


class PharmacyListView(generics.ListAPIView):
	queryset = Pharmacy.objects.filter(is_active=True).order_by('name')
	serializer_class = PharmacySerializer


class PharmacyInventoryListView(generics.ListAPIView):
	serializer_class = PharmacyInventorySerializer

	def get_queryset(self):
		queryset = PharmacyInventory.objects.select_related('pharmacy').filter(is_available=True)
		pharmacy_id = self.request.query_params.get('pharmacy_id')
		q = self.request.query_params.get('q')
		if pharmacy_id:
			queryset = queryset.filter(pharmacy_id=pharmacy_id)
		if q:
			queryset = queryset.filter(drug_name__icontains=q)
		return queryset.order_by('drug_name')


class DeliveryZoneListCreateView(generics.ListCreateAPIView):
	queryset = DeliveryZone.objects.all().order_by('min_radius_km')
	serializer_class = DeliveryZoneSerializer

	def get_permissions(self):
		if self.request.method == 'POST':
			return [IsAdmin()]
		return super().get_permissions()


class DeliveryZoneDetailView(generics.RetrieveUpdateAPIView):
	queryset = DeliveryZone.objects.all()
	serializer_class = DeliveryZoneSerializer
	permission_classes = [IsAdmin]
