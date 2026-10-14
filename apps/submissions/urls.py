from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExpenseCategoryViewSet,
    EarningsSubmissionViewSet,
    ExpenseSubmissionViewSet,
    AttachmentViewSet
)

router = DefaultRouter()
router.register(r'categories', ExpenseCategoryViewSet, basename='category')
router.register(r'earnings', EarningsSubmissionViewSet, basename='earnings')
router.register(r'expenses', ExpenseSubmissionViewSet, basename='expense')
router.register(r'attachments', AttachmentViewSet, basename='attachment')

urlpatterns = [
    path('', include(router.urls)),
]
