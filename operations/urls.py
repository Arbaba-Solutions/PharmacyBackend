from django.urls import path

from operations.views import (
    AdminDriverBalanceAdjustView,
    DistanceEstimateView,
    DriverBalanceTransactionListView,
    DriverTopUpView,
    NotificationCreateView,
    NotificationListView,
    PushDeviceRegisterView,
    PushDeviceUnregisterView,
    PushSendView,
)

urlpatterns = [
    path('driver-balance-transactions/', DriverBalanceTransactionListView.as_view(), name='driver-balance-transactions'),
    path('driver-balance/top-up/', DriverTopUpView.as_view(), name='driver-balance-top-up'),
    path('admin/driver-balance/adjust/', AdminDriverBalanceAdjustView.as_view(), name='admin-driver-balance-adjust'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/create/', NotificationCreateView.as_view(), name='notification-create'),
    path('distance/estimate/', DistanceEstimateView.as_view(), name='distance-estimate'),
    path('push-devices/register/', PushDeviceRegisterView.as_view(), name='push-device-register'),
    path('push-devices/unregister/', PushDeviceUnregisterView.as_view(), name='push-device-unregister'),
    path('push/send/', PushSendView.as_view(), name='push-send'),
]
