from datetime import date
from decimal import Decimal
from django.db.models import Sum, Q, Count, Case, When
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from apps.accounts.permissions import IsAdminUserRole
from . import salary as salary_service

from .models import (
    DriverProfile, Vehicle, DailyEarning, DailyCalculation,
    CNGExpense, Refund, CompanyPayment, SalaryPayment,
    UploadedDocument, AuditLog, AccidentDeduction,
    StatusChoices, PaymentStatusChoices, PaymentModeChoices, WorkingDayChoices
)
from .serializers import (
    DriverProfileSerializer, VehicleSerializer, DailyCalculationSerializer,
    DailyEarningSerializer, CNGExpenseSerializer, RefundSerializer,
    CompanyPaymentSerializer, SalaryPaymentSerializer,
    UploadedDocumentSerializer, AuditLogSerializer, AccidentDeductionSerializer
)

class FleetVehicleViewSet(viewsets.ReadOnlyModelViewSet):
    """Expose fleet.Vehicle objects so submissions use correct vehicle IDs."""
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        try:
            from apps.vehicles.models import Vehicle as AppVehicle
            app_vehicles = AppVehicle.objects.all()
            app_regs = set(app_vehicles.values_list('registration_number', flat=True))
            
            # Prune/deactivate any fleet.Vehicle not in AppVehicle anymore
            orphan_fleet_vehicles = Vehicle.objects.exclude(registration_number__in=app_regs)
            for orphan in orphan_fleet_vehicles:
                try:
                    orphan.delete()
                except Exception:
                    orphan.is_active = False
                    orphan.save(update_fields=['is_active'])

            # Sync any new or active AppVehicle to fleet.Vehicle
            for av in app_vehicles:
                fv, created = Vehicle.objects.get_or_create(
                    registration_number=av.registration_number,
                    defaults={
                        'make': av.make or 'Maruti Suzuki',
                        'model': av.model or 'WagonR CNG',
                        'year': av.year or 2023,
                        'is_active': av.status == av.Status.ACTIVE,
                    }
                )
                if not created:
                    fv.make = av.make or fv.make
                    fv.model = av.model or fv.model
                    fv.year = av.year or fv.year
                    fv.is_active = (av.status == av.Status.ACTIVE)
                    fv.save(update_fields=['make', 'model', 'year', 'is_active'])
        except Exception:
            pass
        return Vehicle.objects.filter(is_active=True).order_by('registration_number')
from .calculations import compute_daily_breakdown

class IsAdminOrOwnerDriver(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_admin:
            return True
        # Driver check
        if hasattr(obj, 'driver'):
            return obj.driver.user == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def live_calculate(request):
    """
    Live immediate recalculation API without persisting.
    Supports:
    1. 50% Profit-Sharing Mode (Exact 8-step formula)
    2. Fixed Rent Mode (Half Day ₹650 / Full Day ₹1,200)
    """
    data = request.data
    mode = data.get('payment_mode', 'REVENUE_SHARING')
    working_day = data.get('working_day_type', 'FULL_DAY')

    if mode == 'FIXED_RENT':
        rent_amt = Decimal('650.00') if str(working_day).upper() == 'HALF_DAY' else Decimal('1200.00')
        return Response({
            'payment_mode': 'FIXED_RENT',
            'working_day_type': working_day,
            'rent_due': str(rent_amt),
            'driver_salary': '0.00',
            'tourbee_share': '0.00',
            'final_gpay_amount': '0.00',
            'total_uber_earnings': '0.00',
            'passenger_cash_collected': '0.00',
            'wallet_difference': '0.00',
            'expenses': '0.00',
            'cng_expense': '0.00',
            'refund': '0.00',
            'profit_amount': '0.00',
            'A': '0.00',
            'B': '0.00',
            'C': '0.00',
            'D': '0.00',
            'E': '0.00',
            'F': '0.00',
            'G': '0.00',
            'driver_share': '0.00',
            'company_share': '0.00',
            'H': '0.00',
            'I': '0.00',
            'J': str(rent_amt),
            'daily_rent_payable': str(rent_amt),
        })

    # 50% Profit-Sharing Mode
    earnings = data.get('total_uber_earnings') if data.get('total_uber_earnings') is not None else data.get('A', 0)
    cash = data.get('passenger_cash_collected') if data.get('passenger_cash_collected') is not None else data.get('B', 0)
    exp = data.get('expenses') if data.get('expenses') is not None else data.get('D', 0)
    cng = data.get('cng_expense') if data.get('cng_expense') is not None else data.get('E', 0)
    ref = data.get('refund') if data.get('refund') is not None else data.get('F', 0)

    res = compute_daily_breakdown(
        total_uber_earnings=earnings,
        passenger_cash_collected=cash,
        expenses=exp,
        cng_expense=cng,
        refund=ref
    )
    res['payment_mode'] = 'REVENUE_SHARING'
    res['rent_due'] = '0.00'
    return Response(res)

class DailyCalculationViewSet(viewsets.ModelViewSet):
    serializer_class = DailyCalculationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = DailyCalculation.objects.all().select_related('driver__user', 'vehicle')
        if not user.is_admin:
            qs = qs.filter(driver__user=user)
        
        driver_param = self.request.query_params.get('driver')
        if driver_param and user.is_admin:
            if str(driver_param).isdigit():
                qs = qs.filter(Q(driver_id=driver_param) | Q(driver__user_id=driver_param))
            else:
                qs = qs.filter(driver__user__username__iexact=driver_param)
        
        date = self.request.query_params.get('date')
        if date:
            qs = qs.filter(date=date)

        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            qs = qs.filter(vehicle_id=vehicle_id)

        vehicle_reg = self.request.query_params.get('vehicle_reg')
        if vehicle_reg:
            qs = qs.filter(vehicle__registration_number__icontains=vehicle_reg)

        payment_mode = self.request.query_params.get('payment_mode')
        if payment_mode:
            qs = qs.filter(payment_mode=payment_mode)

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.upper())

        month = self.request.query_params.get('month') # YYYY-MM
        if month:
            parts = month.split('-')
            if len(parts) == 2:
                qs = qs.filter(date__year=parts[0], date__month=parts[1])

        return qs.order_by('-date', '-created_at')

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_admin:
            profile = DriverProfile.objects.filter(user=user).first()
            if not profile:
                # Auto-create from apps.drivers.Driver
                try:
                    from apps.drivers.models import Driver as AppDriver
                    app_driver = AppDriver.objects.filter(user=user).first()
                    if app_driver:
                        mode = PaymentModeChoices.REVENUE_SHARING if app_driver.driver_type == AppDriver.DriverType.PROFIT_SHARING else PaymentModeChoices.FIXED_RENT
                        license_num = app_driver.license_number or f"LIC-{user.id}"
                        existing = DriverProfile.objects.filter(license_number=license_num).first()
                        if existing and existing.user != user:
                            license_num = f"{license_num}-{user.id}"
                        profile, _ = DriverProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                'payment_mode': mode,
                                'phone': user.phone_number or '',
                                'license_number': license_num,
                                'is_active': app_driver.is_active,
                            }
                        )
                except Exception:
                    pass
            if not profile:
                raise permissions.PermissionDenied("Driver profile not found.")
            driver_val = profile
        else:
            driver_val = serializer.validated_data.get('driver')
            if not driver_val:
                driver_id = self.request.data.get('driver')
                if driver_id:
                    driver_val = DriverProfile.objects.filter(id=driver_id).first()

        vehicle_val = serializer.validated_data.get('vehicle')
        date_val = serializer.validated_data.get('date')

        # Check for accidental duplicate submissions
        if DailyCalculation.objects.filter(driver=driver_val, vehicle=vehicle_val, date=date_val).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": f"A submission for this driver, vehicle ({vehicle_val.registration_number if vehicle_val else ''}), and date ({date_val}) already exists."})

        extra = {'driver': driver_val}
        if not user.is_admin or not serializer.validated_data.get('payment_mode'):
            if driver_val and driver_val.payment_mode:
                extra['payment_mode'] = driver_val.payment_mode
        if 'cng_bill_file' in self.request.FILES:
            extra['cng_bill_file'] = self.request.FILES['cng_bill_file']
        if 'uber_screenshot_file' in self.request.FILES:
            extra['uber_screenshot_file'] = self.request.FILES['uber_screenshot_file']

        instance = serializer.save(**extra)

        AuditLog.objects.create(
            user=user,
            action='CREATE_CALCULATION',
            target_model='DailyCalculation',
            target_id=instance.id,
            new_state={
                'driver': str(instance.driver),
                'date': str(instance.date),
                'payment_mode': instance.payment_mode,
                'final_gpay_or_rent': str(instance.J),
                'status': instance.status
            }
        )

    def perform_update(self, serializer):
        user = self.request.user
        old_obj = self.get_object()
        # Block editing of PAID entries (admin-only override via unlock/mark_status)
        if old_obj.status == 'PAID':
            raise ValidationError({"detail": "Cannot edit a Paid entry. Mark it Pending first."})
        if old_obj.is_locked and not user.is_admin:
            raise permissions.PermissionDenied("This calculation is locked and can only be modified by company admin.")
        
        extra = {}
        if 'cng_bill_file' in self.request.FILES:
            extra['cng_bill_file'] = self.request.FILES['cng_bill_file']
        if 'uber_screenshot_file' in self.request.FILES:
            extra['uber_screenshot_file'] = self.request.FILES['uber_screenshot_file']

        instance = serializer.save(**extra)
        AuditLog.objects.create(
            user=user,
            action='UPDATE_CALCULATION',
            target_model='DailyCalculation',
            target_id=instance.id,
            new_state={'final_gpay_or_rent': str(instance.J), 'status': instance.status},
            remarks=self.request.data.get('audit_remarks', '')
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        # Block deletion of PAID entries
        if obj.status == 'PAID':
            return Response(
                {"detail": "Cannot delete a Paid entry. Mark it Pending first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def mark_status(self, request, pk=None):
        calc = self.get_object()
        new_status = request.data.get('status', 'PAID').upper()
        if new_status in ['PAID', 'PENDING']:
            calc.status = new_status
            calc.save()
            return Response({'id': calc.id, 'status': calc.status, 'payment_status': calc.status})
        return Response({'error': 'Invalid status. Must be PAID or PENDING.'}, status=400)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def lock(self, request, pk=None):
        calc = self.get_object()
        calc.is_locked = True
        calc.locked_at = timezone.now()
        calc.locked_by = request.user
        calc.save()
        AuditLog.objects.create(
            user=request.user,
            action='LOCK_CALCULATION',
            target_model='DailyCalculation',
            target_id=calc.id
        )
        return Response({'status': 'locked', 'id': calc.id})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def unlock(self, request, pk=None):
        calc = self.get_object()
        calc.is_locked = False
        calc.save()
        AuditLog.objects.create(
            user=request.user,
            action='UNLOCK_CALCULATION',
            target_model='DailyCalculation',
            target_id=calc.id,
            remarks=request.data.get('reason', '')
        )
        return Response({'status': 'unlocked', 'id': calc.id})

class DailyEarningViewSet(viewsets.ModelViewSet):
    serializer_class = DailyEarningSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = DailyEarning.objects.all().select_related('driver__user', 'vehicle')
        if not user.is_admin:
            qs = qs.filter(driver__user=user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_admin:
            profile = DriverProfile.objects.get(user=user)
            earning = serializer.save(driver=profile)
        else:
            earning = serializer.save()
        
        # Automatically create or sync DailyCalculation
        cng_sum = CNGExpense.objects.filter(
            driver=earning.driver,
            date=earning.date,
            status=StatusChoices.APPROVED
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        calc, _ = DailyCalculation.objects.get_or_create(
            driver=earning.driver,
            date=earning.date,
            defaults={'vehicle': earning.vehicle}
        )
        calc.vehicle = earning.vehicle
        calc.A = earning.total_uber_earnings
        calc.B = earning.cash_collected
        calc.D = earning.uber_charge
        calc.E = cng_sum
        calc.F = earning.refund
        calc.daily_earning = earning
        calc.save()

class CNGExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = CNGExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = CNGExpense.objects.all().select_related('driver__user', 'vehicle')
        if not user.is_admin:
            qs = qs.filter(driver__user=user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_admin:
            profile = DriverProfile.objects.get(user=user)
            serializer.save(driver=profile)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def approve(self, request, pk=None):
        expense = self.get_object()
        expense.status = StatusChoices.APPROVED
        expense.admin_remarks = request.data.get('remarks', '')
        expense.save()

        # Update DailyCalculation variable E
        cng_sum = CNGExpense.objects.filter(
            driver=expense.driver,
            date=expense.date,
            status=StatusChoices.APPROVED
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        calc = DailyCalculation.objects.filter(driver=expense.driver, date=expense.date).first()
        if calc and not calc.is_locked:
            calc.E = cng_sum
            calc.save()

        return Response({'status': 'approved', 'id': expense.id})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def reject(self, request, pk=None):
        expense = self.get_object()
        expense.status = StatusChoices.REJECTED
        expense.admin_remarks = request.data.get('remarks', '')
        expense.save()
        return Response({'status': 'rejected', 'id': expense.id})

class CompanyPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = CompanyPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = CompanyPayment.objects.all().select_related('driver__user', 'vehicle', 'daily_calculation')
        if not user.is_admin:
            qs = qs.filter(driver__user=user)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_admin:
            profile = DriverProfile.objects.get(user=user)
            serializer.save(driver=profile, status=PaymentStatusChoices.PENDING)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def confirm(self, request, pk=None):
        payment = self.get_object()
        payment.status = PaymentStatusChoices.COMPLETED
        payment.confirmed_by = request.user
        payment.confirmed_at = timezone.now()
        payment.save()
        return Response({'status': 'confirmed', 'id': payment.id})

def _parse_query_date(request, name):
    """Parse an optional YYYY-MM-DD query parameter; 400 on a malformed value."""
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError({name: ['Use the format YYYY-MM-DD.']})


def _fmt_date(d):
    return d.strftime('%d-%m-%Y') if d else None


def _totals_payload(totals):
    return {
        'total_salary': str(totals['total_salary']),
        'paid_salary': str(totals['paid_salary']),
        'salary_balance': str(totals['salary_balance']),
        'status': totals['status'],
        'has_salary': totals['has_salary'],
        'days_counted': totals['days_counted'],
        'last_payment_date': _fmt_date(totals['last_payment_date']),
    }


def _driver_identity(profile):
    return {
        'driver_id': profile.id,
        'driver_name': profile.user.get_full_name() or profile.user.username,
        'username': profile.user.username,
        'phone': profile.phone,
        'payment_mode': profile.payment_mode,
        'is_active': profile.is_active,
        'assigned_vehicle': profile.assigned_vehicle.registration_number if profile.assigned_vehicle else None,
    }


def _salary_detail(profile, request):
    """Salary summary + payment history + per-day breakdown for ONE driver profile."""
    date_from = _parse_query_date(request, 'date_from')
    date_to = _parse_query_date(request, 'date_to')

    payments = SalaryPayment.objects.filter(driver=profile).select_related('driver__user', 'recorded_by')
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)

    daily = [
        {
            'id': c.id,
            'date': _fmt_date(c.date),
            'date_iso': c.date.isoformat(),
            'vehicle_reg': c.vehicle.registration_number,
            'profit_amount': str(c.G),
            'driver_salary': str(c.driver_share),
        }
        for c in salary_service.daily_salary_rows(profile.id, date_from, date_to)[:500]
    ]

    return {
        **_driver_identity(profile),
        'salary_applicable': profile.payment_mode == PaymentModeChoices.REVENUE_SHARING,
        **_totals_payload(salary_service.salary_totals(profile.id)),
        'payments': SalaryPaymentSerializer(payments[:500], many=True).data,
        'daily_salary': daily,
    }


class SalaryPaymentViewSet(viewsets.ModelViewSet):
    """
    Salary payments (existing SalaryPayment model).

    * list / retrieve: admin sees every driver (filter: ?driver=<id>&date_from=&date_to=),
      a driver only ever sees their own rows.
    * create / update / delete: admin only. All writes go through ``fleet.salary`` which
      validates the amount server-side under a row lock and writes an audit log entry.
    """
    serializer_class = SalaryPaymentSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

    def get_queryset(self):
        user = self.request.user
        qs = SalaryPayment.objects.all().select_related('driver__user', 'recorded_by')
        if not user.is_admin:
            return qs.filter(driver__user=user)

        driver_id = self.request.query_params.get('driver')
        if driver_id:
            if not str(driver_id).isdigit():
                raise ValidationError({'driver': ['Driver must be a numeric id.']})
            qs = qs.filter(driver_id=driver_id)
        date_from = _parse_query_date(self.request, 'date_from')
        date_to = _parse_query_date(self.request, 'date_to')
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)
        if date_to:
            qs = qs.filter(payment_date__lte=date_to)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        payment, created = salary_service.record_salary_payment(
            driver_id=data['driver'].id,
            amount=data['amount'],
            payment_date=data.get('payment_date'),
            recorded_by=request.user,
            payment_method=data.get('payment_method'),
            transaction_reference=data.get('transaction_reference'),
            notes=data.get('notes'),
            month=data.get('month'),
            receipt_file=data.get('receipt_file'),
            idempotency_key=(data.get('idempotency_key') or '').strip() or None,
        )
        body = SalaryPaymentSerializer(payment, context=self.get_serializer_context()).data
        body['duplicate'] = not created
        body['salary_summary'] = _totals_payload(salary_service.salary_totals(payment.driver_id))
        return Response(body, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        payment = self.get_object()
        serializer = self.get_serializer(payment, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'driver' in data and data['driver'].id != payment.driver_id:
            raise ValidationError({'driver': ['A payment cannot be moved to a different driver.']})
        changes = {
            k: v for k, v in data.items()
            if k in ('amount', 'payment_date', 'transaction_reference', 'notes', 'payment_method')
        }
        payment = salary_service.update_salary_payment(payment.id, user=request.user, **changes)
        return Response(SalaryPaymentSerializer(payment, context=self.get_serializer_context()).data)

    def destroy(self, request, *args, **kwargs):
        salary_service.delete_salary_payment(self.get_object(), user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_salary(request):
    """The logged-in driver's own salary: totals, payment history, per-day breakdown."""
    profile = (
        DriverProfile.objects.filter(user=request.user)
        .select_related('user', 'assigned_vehicle').first()
    )
    if not profile:
        # Try to auto-create from apps.drivers.Driver
        try:
            from apps.drivers.models import Driver as AppDriver
            app_driver = AppDriver.objects.filter(user=request.user).first()
            if app_driver:
                mode = PaymentModeChoices.REVENUE_SHARING if app_driver.driver_type == AppDriver.DriverType.PROFIT_SHARING else PaymentModeChoices.FIXED_RENT
                fleet_veh = None
                if app_driver.assigned_vehicle:
                    fleet_veh = Vehicle.objects.filter(
                        registration_number=app_driver.assigned_vehicle.registration_number
                    ).first()
                    if not fleet_veh:
                        fleet_veh = Vehicle.objects.create(
                            registration_number=app_driver.assigned_vehicle.registration_number,
                            make=app_driver.assigned_vehicle.make or 'Maruti Suzuki',
                            model=app_driver.assigned_vehicle.model or 'WagonR CNG',
                            year=app_driver.assigned_vehicle.year or 2023,
                            is_active=True,
                        )
                license_num = app_driver.license_number or f"LIC-{request.user.id}"
                existing = DriverProfile.objects.filter(license_number=license_num).first()
                if existing and existing.user != request.user:
                    license_num = f"{license_num}-{request.user.id}"
                profile, _ = DriverProfile.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'payment_mode': mode,
                        'phone': request.user.phone_number or '',
                        'license_number': license_num,
                        'assigned_vehicle': fleet_veh,
                        'is_active': app_driver.is_active,
                    }
                )
        except Exception:
            pass
        # If still no profile, create a basic one for any DRIVER-role user
        if not profile and getattr(request.user, 'role', None) == 'DRIVER':
            try:
                license_num = f"LIC-{request.user.id}"
                existing = DriverProfile.objects.filter(license_number=license_num).first()
                if existing and existing.user != request.user:
                    license_num = f"LIC-{request.user.id}-X"
                profile, _ = DriverProfile.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'payment_mode': PaymentModeChoices.REVENUE_SHARING,
                        'phone': request.user.phone_number or '',
                        'license_number': license_num,
                        'is_active': True,
                    }
                )
            except Exception:
                pass
        if not profile:
            return Response({'error': 'Driver profile not found'}, status=404)
    return Response(_salary_detail(profile, request))


@api_view(['GET'])
@permission_classes([IsAdminUserRole])
def salary_overview(request):
    # Ensure all App Drivers exist in Fleet DriverProfile
    try:
        from apps.drivers.models import Driver as AppDriver
        existing_user_ids = set(DriverProfile.objects.values_list('user_id', flat=True))
        missing_drivers = [ad for ad in AppDriver.objects.select_related('user').exclude(user_id__in=existing_user_ids)]
        if missing_drivers:
            for ad in missing_drivers:
                mode = PaymentModeChoices.REVENUE_SHARING if ad.driver_type == AppDriver.DriverType.PROFIT_SHARING else PaymentModeChoices.FIXED_RENT
                lic = ad.license_number or f"LIC-{ad.user_id}"
                if DriverProfile.objects.filter(license_number=lic).exclude(user=ad.user).exists():
                    lic = f"{lic}-{ad.user_id}"
                DriverProfile.objects.get_or_create(
                    user=ad.user,
                    defaults={
                        'payment_mode': mode,
                        'phone': ad.user.phone_number or '',
                        'license_number': lic,
                        'is_active': ad.is_active,
                    }
                )
    except Exception:
        pass

    profiles = DriverProfile.objects.select_related('user', 'assigned_vehicle')
    driver_id = request.query_params.get('driver')
    if driver_id:
        if not str(driver_id).isdigit():
            raise ValidationError({'driver': ['Driver must be a numeric id.']})
        profiles = profiles.filter(id=driver_id)

    profiles = list(profiles)
    totals_by_driver = salary_service.salary_totals_by_driver([p.id for p in profiles])

    rows = []
    for p in profiles:
        t = totals_by_driver.get(p.id, {
            'total_salary': Decimal('0.00'),
            'paid_salary': Decimal('0.00'),
            'salary_balance': Decimal('0.00'),
            'status': 'PAID',
            'has_salary': False,
            'days_counted': 0,
            'last_payment_date': None,
        })
        # Include all 50% profit-sharing drivers so admin can select and record payments
        if p.payment_mode == PaymentModeChoices.REVENUE_SHARING or t.get('has_salary'):
            rows.append({**_driver_identity(p), **_totals_payload(t)})

    grand_total = sum((Decimal(r['total_salary']) for r in rows), Decimal('0.00'))
    grand_paid = sum((Decimal(r['paid_salary']) for r in rows), Decimal('0.00'))
    return Response({
        'drivers': rows,
        'totals': {
            'total_salary': str(grand_total),
            'paid_salary': str(grand_paid),
            'salary_balance': str(grand_total - grand_paid),
            'drivers_pending': sum(1 for r in rows if r['status'] == 'PENDING'),
        },
    })


@api_view(['GET'])
@permission_classes([IsAdminUserRole])
def salary_driver_detail(request, pk):
    """Admin: one driver's salary summary, full payment history and per-day breakdown."""
    profile = (
        DriverProfile.objects.filter(pk=pk)
        .select_related('user', 'assigned_vehicle').first()
    )
    if not profile:
        return Response({'error': 'Driver not found'}, status=404)
    return Response(_salary_detail(profile, request))

class AccidentDeductionViewSet(viewsets.ModelViewSet):
    serializer_class = AccidentDeductionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AccidentDeduction.objects.all().select_related('driver__user', 'approved_by')
        if not user.is_admin:
            qs = qs.filter(driver__user=user)

        driver_id = self.request.query_params.get('driver')
        if driver_id and user.is_admin:
            qs = qs.filter(driver_id=driver_id)

        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)

        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_admin:
            instance = serializer.save(
                approved_by=user,
                approved_at=timezone.now(),
                status=StatusChoices.APPROVED
            )
        else:
            profile = DriverProfile.objects.get(user=user)
            instance = serializer.save(
                driver=profile,
                status=StatusChoices.PENDING
            )

        AuditLog.objects.create(
            user=user,
            action='CREATE_DEDUCTION',
            target_model='AccidentDeduction',
            target_id=instance.id,
            new_state={
                'driver': str(instance.driver),
                'amount': str(instance.amount),
                'reason': instance.reason,
                'status': instance.status
            }
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def approve(self, request, pk=None):
        deduction = self.get_object()
        deduction.status = StatusChoices.APPROVED
        deduction.approved_by = request.user
        deduction.approved_at = timezone.now()
        deduction.save()

        AuditLog.objects.create(
            user=request.user,
            action='APPROVE_DEDUCTION',
            target_model='AccidentDeduction',
            target_id=deduction.id,
            new_state={'status': 'APPROVED', 'amount': str(deduction.amount)}
        )
        return Response({'status': 'approved', 'id': deduction.id})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    def reject(self, request, pk=None):
        deduction = self.get_object()
        deduction.status = StatusChoices.REJECTED
        deduction.save()

        AuditLog.objects.create(
            user=request.user,
            action='REJECT_DEDUCTION',
            target_model='AccidentDeduction',
            target_id=deduction.id,
            new_state={'status': 'REJECTED'}
        )
        return Response({'status': 'rejected', 'id': deduction.id})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def fleet_dashboard(request):
    """
    Dashboard metrics strictly conforming to TourBee specifications:
    ADMIN:
    - Total number of active drivers
    - Drivers using 50% mode
    - Drivers using fixed-rent mode
    - Total daily Uber earnings (50% mode only)
    - Total driver salaries (50% mode only)
    - Total TourBee shares (50% mode only)
    - Total GPay amounts pending
    - Total fixed rent pending
    - Total payments received
    - Recent driver submissions
    Filters supported: Date, Driver, Vehicle Number, Payment Mode, Payment Status.

    DRIVER:
    Strictly segregated by assigned payment mode:
    - 50% Mode: daily submission, CNG upload, screenshot upload, summary, driver salary, TourBee share, GPay, payment history.
    - Fixed Rent Mode: daily rent submission, Half Day / Full Day, rent due, payment status, rent payment history.
    """
    user = request.user
    today = timezone.localdate()

    if user.is_admin:
        # Active driver counts in single query
        driver_stats = DriverProfile.objects.filter(is_active=True).aggregate(
            active=Count('id'),
            mode_50=Count(Case(When(payment_mode=PaymentModeChoices.REVENUE_SHARING, then=1))),
            mode_rent=Count(Case(When(payment_mode=PaymentModeChoices.FIXED_RENT, then=1))),
        )
        active_drivers = driver_stats['active'] or 0
        drivers_50_mode = driver_stats['mode_50'] or 0
        drivers_rent_mode = driver_stats['mode_rent'] or 0

        # Build filtered queryset for calculations
        calcs = DailyCalculation.objects.all().select_related('driver__user', 'vehicle')
        
        date_param = request.query_params.get('date')
        if date_param:
            calcs = calcs.filter(date=date_param)
        
        driver_param = request.query_params.get('driver')
        if driver_param:
            calcs = calcs.filter(driver_id=driver_param)
        
        vehicle_param = request.query_params.get('vehicle')
        if vehicle_param:
            calcs = calcs.filter(vehicle_id=vehicle_param)
        
        vehicle_reg = request.query_params.get('vehicle_reg')
        if vehicle_reg:
            calcs = calcs.filter(vehicle__registration_number__icontains=vehicle_reg)
        
        mode_param = request.query_params.get('payment_mode')
        if mode_param:
            calcs = calcs.filter(payment_mode=mode_param)
        
        status_param = request.query_params.get('status')
        if status_param:
            calcs = calcs.filter(status=status_param.upper())

        # Calculations in single batched conditional aggregation
        agg_calcs = calcs.aggregate(
            total_uber=Sum(Case(When(payment_mode=PaymentModeChoices.REVENUE_SHARING, then='A'), default=Decimal('0.00'))),
            total_driver_salaries=Sum(Case(When(payment_mode=PaymentModeChoices.REVENUE_SHARING, then='driver_share'), default=Decimal('0.00'))),
            total_tourbee_shares=Sum(Case(When(payment_mode=PaymentModeChoices.REVENUE_SHARING, then='company_share'), default=Decimal('0.00'))),
            total_gpay_pending=Sum(Case(When(payment_mode=PaymentModeChoices.REVENUE_SHARING, status=PaymentStatusChoices.PENDING, then='J'), default=Decimal('0.00'))),
            total_gpay_paid=Sum(Case(When(payment_mode=PaymentModeChoices.REVENUE_SHARING, status=PaymentStatusChoices.PAID, then='J'), default=Decimal('0.00'))),
            total_fixed_rent_pending=Sum(Case(When(payment_mode=PaymentModeChoices.FIXED_RENT, status=PaymentStatusChoices.PENDING, then='J'), default=Decimal('0.00'))),
            total_fixed_rent_paid=Sum(Case(When(payment_mode=PaymentModeChoices.FIXED_RENT, status=PaymentStatusChoices.PAID, then='J'), default=Decimal('0.00'))),
        )
        total_daily_uber_earnings = agg_calcs['total_uber'] or Decimal('0.00')
        total_driver_salaries = agg_calcs['total_driver_salaries'] or Decimal('0.00')
        total_tourbee_shares = agg_calcs['total_tourbee_shares'] or Decimal('0.00')
        total_gpay_pending = agg_calcs['total_gpay_pending'] or Decimal('0.00')
        total_gpay_paid = agg_calcs['total_gpay_paid'] or Decimal('0.00')
        total_fixed_rent_pending = agg_calcs['total_fixed_rent_pending'] or Decimal('0.00')
        total_fixed_rent_paid = agg_calcs['total_fixed_rent_paid'] or Decimal('0.00')
        total_payments_received = total_gpay_paid + total_fixed_rent_paid

        # Recent driver submissions
        recent_submissions = DailyCalculationSerializer(calcs.order_by('-date', '-created_at')[:20], many=True, context={'request': request}).data

        # Salary Payments made to drivers
        salary_paid_agg = SalaryPayment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_salary_paid = salary_paid_agg
        total_salary_balance = max(Decimal('0.00'), total_driver_salaries - total_salary_paid)

        return Response({
            'role': 'ADMIN',
            'active_drivers_count': active_drivers,
            'drivers_50_mode_count': drivers_50_mode,
            'drivers_rent_mode_count': drivers_rent_mode,
            'total_daily_uber_earnings': str(total_daily_uber_earnings),
            'total_driver_salaries': str(total_driver_salaries),
            'total_salary_paid': str(total_salary_paid),
            'total_salary_balance': str(total_salary_balance),
            'total_tourbee_shares': str(total_tourbee_shares),
            'total_gpay_pending': str(total_gpay_pending),
            'total_gpay_paid': str(total_gpay_paid),
            'total_fixed_rent_pending': str(total_fixed_rent_pending),
            'total_fixed_rent_paid': str(total_fixed_rent_paid),
            'total_payments_received': str(total_payments_received),
            'recent_submissions': recent_submissions,
        })
    else:
        # Driver Dashboard: driver can only see their own information
        profile = DriverProfile.objects.filter(user=user).first()
        if not profile:
            # Try to auto-create from apps.drivers.Driver
            try:
                from apps.drivers.models import Driver as AppDriver
                app_driver = AppDriver.objects.filter(user=user).first()
                if app_driver:
                    mode = PaymentModeChoices.REVENUE_SHARING if app_driver.driver_type == AppDriver.DriverType.PROFIT_SHARING else PaymentModeChoices.FIXED_RENT
                    fleet_veh = None
                    if app_driver.assigned_vehicle:
                        fleet_veh = Vehicle.objects.filter(
                            registration_number=app_driver.assigned_vehicle.registration_number
                        ).first()
                        if not fleet_veh:
                            fleet_veh = Vehicle.objects.create(
                                registration_number=app_driver.assigned_vehicle.registration_number,
                                make=app_driver.assigned_vehicle.make or 'Maruti Suzuki',
                                model=app_driver.assigned_vehicle.model or 'WagonR CNG',
                                year=app_driver.assigned_vehicle.year or 2023,
                                is_active=True,
                            )
                    license_num = app_driver.license_number or f"LIC-{user.id}"
                    existing = DriverProfile.objects.filter(license_number=license_num).first()
                    if existing and existing.user != user:
                        license_num = f"{license_num}-{user.id}"
                    profile, _ = DriverProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'payment_mode': mode,
                            'phone': user.phone_number or '',
                            'license_number': license_num,
                            'assigned_vehicle': fleet_veh,
                            'is_active': app_driver.is_active,
                        }
                    )
            except Exception:
                pass
        # Fallback: create a basic fleet profile for any DRIVER-role user
        if not profile and getattr(user, 'role', None) == 'DRIVER':
            try:
                license_num = f"LIC-{user.id}"
                existing = DriverProfile.objects.filter(license_number=license_num).first()
                if existing and existing.user != user:
                    license_num = f"LIC-{user.id}-X"
                profile, _ = DriverProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'payment_mode': PaymentModeChoices.REVENUE_SHARING,
                        'phone': user.phone_number or '',
                        'license_number': license_num,
                        'is_active': True,
                    }
                )
            except Exception:
                pass
        if not profile:
            return Response({'error': 'Driver profile not found'}, status=404)

        my_calcs = DailyCalculation.objects.filter(driver=profile).select_related('vehicle').order_by('-date', '-created_at')
        today_calc = my_calcs.filter(date=today).first()
        is_rent_driver = (profile.payment_mode == PaymentModeChoices.FIXED_RENT)

        assigned_reg = profile.assigned_vehicle.registration_number if profile.assigned_vehicle else None

        if is_rent_driver:
            # Fixed Rent Dashboard - strictly no 50% salary or TourBee share
            rent_calcs = my_calcs.filter(payment_mode=PaymentModeChoices.FIXED_RENT)
            rent_agg = rent_calcs.aggregate(
                total=Sum('J'),
                pending=Sum(Case(When(status=PaymentStatusChoices.PENDING, then='J'), default=Decimal('0.00'))),
                paid=Sum(Case(When(status=PaymentStatusChoices.PAID, then='J'), default=Decimal('0.00'))),
            )
            total_rent_due = rent_agg['total'] or Decimal('0.00')
            rent_pending = rent_agg['pending'] or Decimal('0.00')
            rent_paid = rent_agg['paid'] or Decimal('0.00')

            return Response({
                'role': 'DRIVER',
                'payment_mode': 'FIXED_RENT',
                'driver_name': user.get_full_name() or user.username,
                'phone': profile.phone,
                'assigned_vehicle': assigned_reg,
                'assigned_vehicle_id': profile.assigned_vehicle_id,
                'total_rent_due': str(total_rent_due),
                'total_rent_pending': str(rent_pending),
                'total_rent_paid': str(rent_paid),
                'today_submission': DailyCalculationSerializer(today_calc, context={'request': request}).data if today_calc else None,
                'recent_submissions': DailyCalculationSerializer(rent_calcs[:15], many=True, context={'request': request}).data,
            })
        else:
            # 50% Profit-Sharing Dashboard
            calcs_50 = my_calcs.filter(payment_mode=PaymentModeChoices.REVENUE_SHARING)
            agg = calcs_50.aggregate(
                total_uber=Sum('A'),
                total_driver_salaries=Sum('driver_share'),
                total_tourbee_shares=Sum('company_share'),
                gpay_pending=Sum(Case(When(status=PaymentStatusChoices.PENDING, then='J'), default=Decimal('0.00'))),
                gpay_paid=Sum(Case(When(status=PaymentStatusChoices.PAID, then='J'), default=Decimal('0.00'))),
            )
            gpay_pending = agg['gpay_pending'] or Decimal('0.00')
            gpay_paid = agg['gpay_paid'] or Decimal('0.00')

            return Response({
                'role': 'DRIVER',
                'payment_mode': 'REVENUE_SHARING',
                'driver_name': user.get_full_name() or user.username,
                'phone': profile.phone,
                'assigned_vehicle': assigned_reg,
                'assigned_vehicle_id': profile.assigned_vehicle_id,
                'total_uber_earnings': str(agg['total_uber'] or '0.00'),
                'total_driver_salary': str(agg['total_driver_salaries'] or '0.00'),
                'total_tourbee_share': str(agg['total_tourbee_shares'] or '0.00'),
                'total_gpay_pending': str(gpay_pending),
                'total_gpay_paid': str(gpay_paid),
                'today_submission': DailyCalculationSerializer(today_calc, context={'request': request}).data if today_calc else None,
                'recent_submissions': DailyCalculationSerializer(calcs_50[:15], many=True, context={'request': request}).data,
            })

