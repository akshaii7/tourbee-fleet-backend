from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BusinessSettingsView,
    SalaryCalculationViewSet,
    SalaryPaymentViewSet,
    RentPaymentViewSet,
    RentSummaryView
)

router = DefaultRouter()
router.register(r'salary-calculations', SalaryCalculationViewSet, basename='salary-calculation')
router.register(r'salary-payments', SalaryPaymentViewSet, basename='salary-payment')
router.register(r'rent-payments', RentPaymentViewSet, basename='rent-payment')

urlpatterns = [
    path('settings/', BusinessSettingsView.as_view(), name='business-settings'),
    path('rent-summary/', RentSummaryView.as_view(), name='rent-summary'),
    path('', include(router.urls)),
]
