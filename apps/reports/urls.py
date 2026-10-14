from django.urls import path
from .views import DashboardSummaryView, FinancialReportsView, ExportDataView

urlpatterns = [
    path('dashboard/', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('financial/', FinancialReportsView.as_view(), name='financial-reports'),
    path('export/', ExportDataView.as_view(), name='export-data'),
]
