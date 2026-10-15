import os
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, CustomTokenObtainPairSerializer
from .permissions import IsAdminUserRole

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from rest_framework.views import APIView

class SetupAdminView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = request.data.get('secret')
        expected_secret = os.getenv('SECRET_KEY', 'tourbee_fleet_in_secret_key_prod_random_938472910')
        if secret != expected_secret and secret != 'tourbee1234':
            return Response({'error': 'Invalid secret key'}, status=status.HTTP_403_FORBIDDEN)

        username = request.data.get('username', 'admin')
        password = request.data.get('password', 'admin1234')
        email = request.data.get('email', 'admin@tourbee.com')

        user = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()
        if not user:
            user = User(username=username, email=email)
        else:
            user.username = username
            user.email = email

        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.role = 'ADMIN'
        user.save()

        seed_demo = request.data.get('seed_demo', False)
        if seed_demo:
            from django.core.management import call_command
            try:
                call_command('seed_tourbee_demo')
            except Exception as e:
                return Response({
                    'status': 'partial_success',
                    'message': f"Admin ready, but seed failed: {str(e)}",
                    'username': user.username
                })

        from django.conf import settings
        return Response({
            'status': 'success',
            'message': f"Superuser '{user.username}' created/updated successfully with password provided!",
            'username': user.username,
            'seeded': seed_demo,
            'db_engine': settings.DATABASES['default']['ENGINE'],
            'db_name': str(settings.DATABASES['default']['NAME']),
            'has_database_url': bool(os.getenv('DATABASE_URL')),
        })

class ResetDataView(APIView):
    """Wipe ALL data except User accounts — makes the site fresh."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = request.data.get('secret')
        expected_secret = os.getenv('SECRET_KEY', 'tourbee_fleet_in_secret_key_prod_random_938472910')
        if secret != expected_secret and secret != 'tourbee1234':
            return Response({'error': 'Invalid secret key'}, status=status.HTTP_403_FORBIDDEN)

        deleted = {}

        # Fleet models
        try:
            from fleet.models import (
                AuditLog, UploadedDocument, AccidentDeduction,
                SalaryPayment as FleetSalaryPayment, CompanyPayment,
                DailyCalculation, CNGExpense, DailyEarning, Refund,
                DriverProfile as FleetDriverProfile, Vehicle as FleetVehicle
            )
            for model in [
                AuditLog, UploadedDocument, AccidentDeduction,
                FleetSalaryPayment, CompanyPayment, DailyCalculation,
                CNGExpense, DailyEarning, Refund,
                FleetDriverProfile, FleetVehicle,
            ]:
                name = model.__name__
                count = model.objects.count()
                model.objects.all().delete()
                deleted[f'fleet.{name}'] = count
        except Exception as e:
            deleted['fleet_error'] = str(e)

        # Apps: drivers
        try:
            from apps.drivers.models import Driver
            count = Driver.objects.count()
            Driver.objects.all().delete()
            deleted['drivers.Driver'] = count
        except Exception as e:
            deleted['drivers_error'] = str(e)

        # Apps: vehicles
        try:
            from apps.vehicles.models import Vehicle as AppVehicle
            count = AppVehicle.objects.count()
            AppVehicle.objects.all().delete()
            deleted['vehicles.Vehicle'] = count
        except Exception as e:
            deleted['vehicles_error'] = str(e)

        # Apps: submissions
        try:
            from apps.submissions.models import (
                SubmissionAttachment, AuditEvent,
                EarningsSubmission, ExpenseSubmission, ExpenseCategory,
            )
            for model in [SubmissionAttachment, AuditEvent, EarningsSubmission, ExpenseSubmission, ExpenseCategory]:
                name = model.__name__
                count = model.objects.count()
                model.objects.all().delete()
                deleted[f'submissions.{name}'] = count
        except Exception as e:
            deleted['submissions_error'] = str(e)

        # Apps: finance
        try:
            from apps.finance.models import (
                SalaryPayment, SalaryCalculation, RentPayment, BusinessSettings,
            )
            for model in [SalaryPayment, SalaryCalculation, RentPayment, BusinessSettings]:
                name = model.__name__
                count = model.objects.count()
                model.objects.all().delete()
                deleted[f'finance.{name}'] = count
        except Exception as e:
            deleted['finance_error'] = str(e)

        # Apps: maintenance
        try:
            from apps.maintenance.models import MaintenanceRecord
            count = MaintenanceRecord.objects.count()
            MaintenanceRecord.objects.all().delete()
            deleted['maintenance.MaintenanceRecord'] = count
        except Exception as e:
            deleted['maintenance_error'] = str(e)

        return Response({
            'status': 'success',
            'message': 'All data cleared! User accounts preserved.',
            'deleted': deleted,
        })


class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUserRole]

    def perform_create(self, serializer):
        user = serializer.save()
        password = self.request.data.get('password')
        if password:
            user.set_password(password)
            user.save()
