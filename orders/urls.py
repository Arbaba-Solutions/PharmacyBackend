from django.urls import path

from orders.views import (
    BlacklistLogListView,
    DisputeListCreateView,
    OrderDetailView,
    OrderListCreateView,
    PrescriptionApproveView,
    PrescriptionQueueView,
    PrescriptionRejectView,
)

urlpatterns = [
    path('', OrderListCreateView.as_view(), name='order-list-create'),
    path('<uuid:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('prescriptions/queue/', PrescriptionQueueView.as_view(), name='prescription-queue'),
    path('prescriptions/<uuid:pk>/approve/', PrescriptionApproveView.as_view(), name='prescription-approve'),
    path('prescriptions/<uuid:pk>/reject/', PrescriptionRejectView.as_view(), name='prescription-reject'),
    path('disputes/', DisputeListCreateView.as_view(), name='dispute-list-create'),
    path('blacklist-log/', BlacklistLogListView.as_view(), name='blacklist-log-list'),
]
