from django.urls import path

from catalog.views import (
    DeliveryZoneDetailView,
    DeliveryZoneListCreateView,
    PharmacyInventoryListView,
    PharmacyListView,
)

urlpatterns = [
    path('pharmacies/', PharmacyListView.as_view(), name='pharmacy-list'),
    path('inventory/', PharmacyInventoryListView.as_view(), name='inventory-list'),
    path('zones/', DeliveryZoneListCreateView.as_view(), name='zone-list-create'),
    path('zones/<uuid:pk>/', DeliveryZoneDetailView.as_view(), name='zone-detail'),
]
