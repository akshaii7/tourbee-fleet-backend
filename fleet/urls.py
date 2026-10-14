from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DailyCalculationViewSet, DailyEarningViewSet, CNGExpenseViewSet,
    CompanyPaymentViewSet, SalaryPaymentViewSet, AccidentDeductionViewSet,
    FleetVehicleViewSet, live_calculate, fleet_dashboard
)

router = DefaultRouter()
router.register(r'calculations', DailyCalculationViewSet, basename='fleet-calculation')
router.register(r'earnings', DailyEarningViewSet, basename='fleet-earning')
router.register(r'cng', CNGExpenseViewSet, basename='fleet-cng')
router.register(r'deductions', AccidentDeductionViewSet, basename='fleet-deduction')
router.register(r'company-payments', CompanyPaymentViewSet, basename='fleet-company-payment')
router.register(r'salary-payments', SalaryPaymentViewSet, basename='fleet-salary-payment')
router.register(r'vehicles', FleetVehicleViewSet, basename='fleet-vehicle')

urlpatterns = [
    path('calculate/live/', live_calculate, name='fleet-live-calculate'),
    path('dashboard/', fleet_dashboard, name='fleet-dashboard'),
    path('', include(router.urls)),
]
