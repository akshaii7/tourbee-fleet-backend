from rest_framework import viewsets, permissions, filters
from .models import MaintenanceRecord
from .serializers import MaintenanceRecordSerializer
from apps.accounts.permissions import IsAdminUserRole

class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    serializer_class = MaintenanceRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['vehicle__registration_number', 'vendor_garage', 'invoice_number', 'notes']
    ordering_fields = ['date', 'cost', 'created_at']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return MaintenanceRecord.objects.none()

        queryset = MaintenanceRecord.objects.all().select_related('vehicle', 'recorded_by')
        if not user.is_admin:
            # Driver can only view records for their assigned vehicle
            if hasattr(user, 'driver_profile') and user.driver_profile.assigned_vehicle:
                queryset = queryset.filter(vehicle=user.driver_profile.assigned_vehicle)
            else:
                return MaintenanceRecord.objects.none()

        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)

        maintenance_type = self.request.query_params.get('type')
        if maintenance_type:
            queryset = queryset.filter(maintenance_type=maintenance_type)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)
