from django.urls import path

from operations.views import (
    DriverBalanceTransactionListView,
    NotificationCreateView,
    NotificationListView,
)

urlpatterns = [
    path('driver-balance-transactions/', DriverBalanceTransactionListView.as_view(), name='driver-balance-transactions'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/create/', NotificationCreateView.as_view(), name='notification-create'),
]
