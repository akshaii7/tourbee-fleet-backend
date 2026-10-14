from rest_framework import viewsets, permissions, filters
from .models import Vehicle
from .serializers import VehicleSerializer
from apps.accounts.permissions import IsAdminUserRole

class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all().order_by('registration_number')
    serializer_class = VehicleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['registration_number', 'make', 'model', 'rc_number']
    ordering_fields = ['registration_number', 'year', 'insurance_expiry', 'fitness_expiry', 'status']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]
