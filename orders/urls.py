from django.urls import path

from orders.views import (
    BlacklistLogListView,
    DisputeListCreateView,
    DriverAcceptOrderView,
    DriverMarkDeliveredView,
    DriverMarkPurchasedView,
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
    path('<uuid:pk>/driver/accept/', DriverAcceptOrderView.as_view(), name='driver-accept-order'),
    path('<uuid:pk>/driver/purchased/', DriverMarkPurchasedView.as_view(), name='driver-mark-purchased'),
    path('<uuid:pk>/driver/delivered/', DriverMarkDeliveredView.as_view(), name='driver-mark-delivered'),
]
