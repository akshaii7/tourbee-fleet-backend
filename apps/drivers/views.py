from rest_framework import viewsets, permissions, filters, status
from rest_framework.response import Response
from .models import Driver
from .serializers import DriverSerializer, DriverCreateUpdateSerializer
from apps.accounts.permissions import IsAdminUserRole

class DriverViewSet(viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__first_name', 'user__last_name', 'user__username', 'license_number', 'user__phone_number']
    ordering_fields = ['user__first_name', 'joining_date', 'driver_type', 'is_active']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Driver.objects.none()
        if user.is_admin:
            queryset = Driver.objects.all().select_related('user', 'assigned_vehicle')
            driver_type = self.request.query_params.get('driver_type')
            if driver_type:
                queryset = queryset.filter(driver_type=driver_type)
            is_active = self.request.query_params.get('is_active')
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            return queryset
        # If regular driver, only return their own profile
        return Driver.objects.filter(user=user).select_related('user', 'assigned_vehicle')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DriverCreateUpdateSerializer
        return DriverSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]
