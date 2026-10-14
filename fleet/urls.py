from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DailyCalculationViewSet, DailyEarningViewSet, CNGExpenseViewSet,
    CompanyPaymentViewSet, SalaryPaymentViewSet, AccidentDeductionViewSet,
    FleetVehicleViewSet, live_calculate, fleet_dashboard,
    my_salary, salary_overview, salary_driver_detail
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
    path('salary/me/', my_salary, name='fleet-salary-me'),
    path('salary/overview/', salary_overview, name='fleet-salary-overview'),
    path('salary/drivers/<int:pk>/', salary_driver_detail, name='fleet-salary-driver-detail'),
    path('', include(router.urls)),
]
