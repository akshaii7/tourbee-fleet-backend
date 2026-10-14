from rest_framework import viewsets, permissions, status, filters
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

from .models import BusinessSettings, SalaryCalculation, SalaryPayment, RentPayment, CalculationStatus
from .serializers import (
    BusinessSettingsSerializer,
    SalaryCalculationSerializer,
    SalaryPaymentSerializer,
    RentPaymentSerializer
)
from apps.accounts.permissions import IsAdminUserRole
from apps.drivers.models import Driver
from apps.submissions.models import EarningsSubmission, ExpenseSubmission, SubmissionStatus, AuditEvent

class BusinessSettingsView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

    def get(self, request):
        settings_obj = BusinessSettings.get_settings()
        serializer = BusinessSettingsSerializer(settings_obj)
        return Response(serializer.data)

    def put(self, request):
        settings_obj = BusinessSettings.get_settings()
        serializer = BusinessSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SalaryCalculationViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryCalculationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['period_start', 'period_end', 'created_at', 'net_payable_to_driver']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return SalaryCalculation.objects.none()
        
        queryset = SalaryCalculation.objects.all().select_related('driver__user', 'calculated_by').prefetch_related('payments')
        if not user.is_admin:
            if hasattr(user, 'driver_profile'):
                queryset = queryset.filter(driver=user.driver_profile)
            else:
                return SalaryCalculation.objects.none()

        driver_id = self.request.query_params.get('driver')
        if driver_id and user.is_admin:
            queryset = queryset.filter(driver_id=driver_id)

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def compute(self, request):
        """
        Calculates profit-sharing for salary drivers based on approved submissions in date range.
        If save=true, saves the SalaryCalculation record.
        """
        driver_id = request.data.get('driver_id')
        period_start_str = request.data.get('period_start')
        period_end_str = request.data.get('period_end')
        save_record = request.data.get('save', False)

        if not driver_id or not period_start_str or not period_end_str:
            return Response({'error': 'driver_id, period_start, and period_end are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            driver = Driver.objects.get(id=driver_id)
        except Driver.DoesNotExist:
            return Response({'error': 'Driver not found.'}, status=status.HTTP_404_NOT_FOUND)

        if driver.driver_type != Driver.DriverType.PROFIT_SHARING:
            return Response(
                {'error': 'Salary profit-sharing is only applicable for profit-sharing drivers, not daily rent drivers.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Approved Earnings
        earnings_qs = EarningsSubmission.objects.filter(
            driver=driver,
            status=SubmissionStatus.APPROVED,
            date__range=[period_start_str, period_end_str]
        )

        gross_earnings = earnings_qs.aggregate(val=Sum('gross_earnings'))['val'] or Decimal('0.00')
        uber_commission = earnings_qs.aggregate(val=Sum('uber_commission'))['val'] or Decimal('0.00')
        cash_collected = earnings_qs.aggregate(val=Sum('cash_collected'))['val'] or Decimal('0.00')

        # Approved Operating Expenses (only eligible categories!)
        expenses_qs = ExpenseSubmission.objects.filter(
            driver=driver,
            status=SubmissionStatus.APPROVED,
            date__range=[period_start_str, period_end_str],
            category__is_eligible_for_profit_sharing=True
        )

        eligible_expenses = expenses_qs.aggregate(val=Sum('amount'))['val'] or Decimal('0.00')
        # Expenses paid out of pocket by driver
        driver_reimbursements = expenses_qs.filter(paid_by_driver=True).aggregate(val=Sum('amount'))['val'] or Decimal('0.00')

        # Profit Sharing Formula:
        # Distributable profit = Gross Uber earnings - Uber commission - Approved eligible operating expenses
        distributable_profit = gross_earnings - uber_commission - eligible_expenses
        driver_share = (distributable_profit * Decimal('0.50')).quantize(Decimal('0.01'))
        company_share = (distributable_profit * Decimal('0.50')).quantize(Decimal('0.01'))

        # Net payable to driver = Driver share (50%) - Cash collected by driver + Out of pocket reimbursements
        net_payable = driver_share - cash_collected + driver_reimbursements

        calc_data = {
            'driver_id': driver.id,
            'driver_name': driver.full_name,
            'driver_type': driver.driver_type,
            'period_start': period_start_str,
            'period_end': period_end_str,
            'approved_trips_records_count': earnings_qs.count(),
            'approved_expense_records_count': expenses_qs.count(),
            'total_gross_earnings': gross_earnings,
            'total_commission': uber_commission,
            'total_eligible_expenses': eligible_expenses,
            'distributable_profit': distributable_profit,
            'driver_share_50': driver_share,
            'company_share_50': company_share,
            'cash_collected_deduction': cash_collected,
            'driver_reimbursements': driver_reimbursements,
            'net_payable_to_driver': net_payable,
        }

        if save_record:
            calc_record = SalaryCalculation.objects.create(
                driver=driver,
                period_start=period_start_str,
                period_end=period_end_str,
                total_gross_earnings=gross_earnings,
                total_commission=uber_commission,
                total_eligible_expenses=eligible_expenses,
                distributable_profit=distributable_profit,
                driver_share_50=driver_share,
                company_share_50=company_share,
                cash_collected_deduction=cash_collected,
                driver_reimbursements=driver_reimbursements,
                net_payable_to_driver=net_payable,
                status=CalculationStatus.DRAFT,
                calculated_by=request.user,
                notes=request.data.get('notes', '')
            )
            AuditEvent.objects.create(
                target_model='SalaryCalculation',
                target_id=calc_record.id,
                actor=request.user,
                action='CREATE_CALCULATION',
                new_status=CalculationStatus.DRAFT,
                notes=f"Calculated salary for {driver.full_name} ({period_start_str} to {period_end_str})"
            )
            return Response(SalaryCalculationSerializer(calc_record).data, status=status.HTTP_201_CREATED)

        return Response(calc_data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def finalize(self, request, pk=None):
        calc = self.get_object()
        calc.status = CalculationStatus.FINALIZED
        calc.save()
        AuditEvent.objects.create(
            target_model='SalaryCalculation',
            target_id=calc.id,
            actor=request.user,
            action='FINALIZE',
            new_status=CalculationStatus.FINALIZED,
            notes='Finalized salary calculation'
        )
        return Response(SalaryCalculationSerializer(calc).data)

class SalaryPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = SalaryPaymentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['payment_date', 'created_at', 'amount']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return SalaryPayment.objects.none()

        queryset = SalaryPayment.objects.all().select_related('salary_calculation', 'driver__user', 'recorded_by')
        if not user.is_admin:
            if hasattr(user, 'driver_profile'):
                queryset = queryset.filter(driver=user.driver_profile)
            else:
                return SalaryPayment.objects.none()

        driver_id = self.request.query_params.get('driver')
        if driver_id and user.is_admin:
            queryset = queryset.filter(driver_id=driver_id)

        calculation_id = self.request.query_params.get('calculation')
        if calculation_id:
            queryset = queryset.filter(salary_calculation_id=calculation_id)

        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

    @transaction.atomic
    def perform_create(self, serializer):
        payment = serializer.save(recorded_by=self.request.user)
        # Check if calculation is fully paid
        calc = payment.salary_calculation
        total_paid = sum(p.amount for p in calc.payments.all())
        if total_paid >= calc.net_payable_to_driver:
            calc.status = CalculationStatus.PAID
            calc.save()

        AuditEvent.objects.create(
            target_model='SalaryPayment',
            target_id=payment.id,
            actor=self.request.user,
            action='PAYMENT_RECORDED',
            notes=f"Recorded salary payment of ₹{payment.amount} for {payment.driver.full_name}"
        )

class RentPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = RentPaymentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['payment_date', 'created_at', 'amount_paid']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return RentPayment.objects.none()

        queryset = RentPayment.objects.all().select_related('driver__user', 'vehicle', 'recorded_by')
        if not user.is_admin:
            if hasattr(user, 'driver_profile'):
                queryset = queryset.filter(driver=user.driver_profile)
            else:
                return RentPayment.objects.none()

        driver_id = self.request.query_params.get('driver')
        if driver_id and user.is_admin:
            queryset = queryset.filter(driver_id=driver_id)

        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

    @transaction.atomic
    def perform_create(self, serializer):
        payment = serializer.save(recorded_by=self.request.user)
        AuditEvent.objects.create(
            target_model='RentPayment',
            target_id=payment.id,
            actor=self.request.user,
            action='RENT_PAYMENT_RECORDED',
            notes=f"Recorded rent payment of ₹{payment.amount_paid} for {payment.driver.full_name}"
        )

class RentSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        driver_id = request.query_params.get('driver_id')
        user = request.user

        if not user.is_admin:
            if not hasattr(user, 'driver_profile'):
                return Response({'error': 'No driver profile found.'}, status=status.HTTP_404_NOT_FOUND)
            driver = user.driver_profile
        else:
            if not driver_id:
                # Return summary for all rent-based drivers
                rent_drivers = Driver.objects.filter(driver_type=Driver.DriverType.DAILY_RENT)
                results = []
                for d in rent_drivers:
                    results.append(self._get_driver_rent_summary(d))
                return Response(results)
            try:
                driver = Driver.objects.get(id=driver_id)
            except Driver.DoesNotExist:
                return Response({'error': 'Driver not found.'}, status=status.HTTP_404_NOT_FOUND)

        if driver.driver_type != Driver.DriverType.DAILY_RENT:
            return Response({'error': 'Driver is not a daily rent driver.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self._get_driver_rent_summary(driver))

    def _get_driver_rent_summary(self, driver):
        payments = RentPayment.objects.filter(driver=driver)
        total_rent_due = payments.aggregate(val=Sum('amount_due'))['val'] or Decimal('0.00')
        total_rent_paid = payments.aggregate(val=Sum('amount_paid'))['val'] or Decimal('0.00')
        total_days = payments.aggregate(val=Sum('days_count'))['val'] or 0
        outstanding = max(Decimal('0.00'), total_rent_due - total_rent_paid)

        return {
            'driver_id': driver.id,
            'driver_name': driver.full_name,
            'daily_rent_rate': driver.daily_rent_amount,
            'assigned_vehicle_reg': driver.assigned_vehicle.registration_number if driver.assigned_vehicle else None,
            'total_rental_records': payments.count(),
            'total_days_billed': total_days,
            'total_rent_due': total_rent_due,
            'total_rent_paid': total_rent_paid,
            'outstanding_balance': outstanding,
        }
