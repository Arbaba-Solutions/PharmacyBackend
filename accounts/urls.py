from django.urls import path

from accounts.views import (
    AdminCustomerListView,
    AdminCustomerUnblacklistView,
    MeView,
    MyCustomerProfileView,
    MyDriverProfileView,
)

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('profiles/customer/', MyCustomerProfileView.as_view(), name='my-customer-profile'),
    path('profiles/driver/', MyDriverProfileView.as_view(), name='my-driver-profile'),
    path('admin/customers/', AdminCustomerListView.as_view(), name='admin-customer-list'),
    path('admin/customers/<uuid:pk>/unblacklist/', AdminCustomerUnblacklistView.as_view(), name='admin-customer-unblacklist'),
]
