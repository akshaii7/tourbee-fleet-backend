from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView,
    CurrentUserProfileView,
    UserListCreateView,
    SetupAdminView,
    ResetDataView,
    health_check,
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('setup-admin/', SetupAdminView.as_view(), name='setup_admin'),
    path('reset-data/', ResetDataView.as_view(), name='reset_data'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', CurrentUserProfileView.as_view(), name='user_profile'),
    path('users/', UserListCreateView.as_view(), name='user_list_create'),
    path('health/', health_check, name='health_check'),
]
