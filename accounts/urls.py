from django.urls import path

from accounts.views import MeView, MyCustomerProfileView, MyDriverProfileView

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('profiles/customer/', MyCustomerProfileView.as_view(), name='my-customer-profile'),
    path('profiles/driver/', MyDriverProfileView.as_view(), name='my-driver-profile'),
]
