from django.urls import path

from operations.views import (
    DistanceEstimateView,
    DriverBalanceTransactionListView,
    NotificationCreateView,
    NotificationListView,
    PushDeviceRegisterView,
    PushDeviceUnregisterView,
    PushSendView,
)

urlpatterns = [
    path('driver-balance-transactions/', DriverBalanceTransactionListView.as_view(), name='driver-balance-transactions'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/create/', NotificationCreateView.as_view(), name='notification-create'),
    path('distance/estimate/', DistanceEstimateView.as_view(), name='distance-estimate'),
    path('push-devices/register/', PushDeviceRegisterView.as_view(), name='push-device-register'),
    path('push-devices/unregister/', PushDeviceUnregisterView.as_view(), name='push-device-unregister'),
    path('push/send/', PushSendView.as_view(), name='push-send'),
]
