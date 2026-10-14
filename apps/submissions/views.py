from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import (
    ExpenseCategory,
    EarningsSubmission,
    ExpenseSubmission,
    SubmissionAttachment,
    AuditEvent,
    SubmissionStatus
)
from .serializers import (
    ExpenseCategorySerializer,
    EarningsSubmissionSerializer,
    ExpenseSubmissionSerializer,
    SubmissionAttachmentSerializer,
    AuditEventSerializer
)
from apps.accounts.permissions import IsAdminUserRole
from apps.drivers.models import Driver

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by('name')
    serializer_class = ExpenseCategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUserRole()]

class EarningsSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = EarningsSubmissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'created_at', 'gross_earnings', 'status']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return EarningsSubmission.objects.none()
        
        queryset = EarningsSubmission.objects.all().select_related('driver__user', 'vehicle', 'reviewed_by').prefetch_related('attachments')
        
        if not user.is_admin:
            if hasattr(user, 'driver_profile'):
                queryset = queryset.filter(driver=user.driver_profile)
            else:
                return EarningsSubmission.objects.none()

        # Query filters
        driver_id = self.request.query_params.get('driver')
        if driver_id and user.is_admin:
            queryset = queryset.filter(driver_id=driver_id)
            
        vehicle_id = self.request.query_params.get('vehicle')
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)

        submission_status = self.request.query_params.get('status')
        if submission_status:
            queryset = queryset.filter(status=submission_status)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        driver = None
        if user.is_admin:
            driver_id = self.request.data.get('driver')
            if driver_id:
                driver = Driver.objects.get(id=driver_id)
            elif hasattr(user, 'driver_profile'):
                driver = user.driver_profile
        else:
            if not hasattr(user, 'driver_profile'):
                raise ValidationError("Only registered drivers can submit earnings.")
            driver = user.driver_profile

        # Fallback to driver's assigned vehicle if not specified
        vehicle = serializer.validated_data.get('vehicle')
        if not vehicle and driver and driver.assigned_vehicle:
            vehicle = driver.assigned_vehicle

        instance = serializer.save(
            driver=driver,
            vehicle=vehicle,
            status=SubmissionStatus.PENDING
        )

        AuditEvent.objects.create(
            target_model='EarningsSubmission',
            target_id=instance.id,
            actor=user,
            action='SUBMIT',
            new_status=SubmissionStatus.PENDING,
            notes='Initial earnings submission created'
        )

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status == SubmissionStatus.APPROVED and not self.request.user.is_admin:
            raise ValidationError("Approved submissions cannot be modified.")

        old_status = instance.status
        new_status = old_status

        # If driver is updating a correction-requested record, reset to PENDING
        if not self.request.user.is_admin and old_status == SubmissionStatus.CORRECTION_REQUESTED:
            new_status = SubmissionStatus.PENDING

        updated_instance = serializer.save(status=new_status)

        AuditEvent.objects.create(
            target_model='EarningsSubmission',
            target_id=updated_instance.id,
            actor=self.request.user,
            action='UPDATE',
            previous_status=old_status,
            new_status=new_status,
            notes='Submission details updated by user'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def approve(self, request, pk=None):
        instance = self.get_object()
        old_status = instance.status
        instance.status = SubmissionStatus.APPROVED
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.rejection_reason = None
        instance.save()

        AuditEvent.objects.create(
            target_model='EarningsSubmission',
            target_id=instance.id,
            actor=request.user,
            action='APPROVE',
            previous_status=old_status,
            new_status=SubmissionStatus.APPROVED,
            notes=request.data.get('notes', 'Approved by admin')
        )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def reject(self, request, pk=None):
        instance = self.get_object()
        reason = request.data.get('reason')
        if not reason:
            return Response({'error': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = instance.status
        instance.status = SubmissionStatus.REJECTED
        instance.rejection_reason = reason
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.save()

        AuditEvent.objects.create(
            target_model='EarningsSubmission',
            target_id=instance.id,
            actor=request.user,
            action='REJECT',
            previous_status=old_status,
            new_status=SubmissionStatus.REJECTED,
            notes=reason
        )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def request_correction(self, request, pk=None):
        instance = self.get_object()
        notes = request.data.get('notes')
        if not notes:
            return Response({'error': 'Correction notes are required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = instance.status
        instance.status = SubmissionStatus.CORRECTION_REQUESTED
        instance.correction_notes = notes
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.save()

        AuditEvent.objects.create(
            target_model='EarningsSubmission',
            target_id=instance.id,
            actor=request.user,
            action='REQUEST_CORRECTION',
            previous_status=old_status,
            new_status=SubmissionStatus.CORRECTION_REQUESTED,
            notes=notes
        )
        return Response(self.get_serializer(instance).data)

class ExpenseSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSubmissionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date', 'created_at', 'amount', 'status']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ExpenseSubmission.objects.none()

        queryset = ExpenseSubmission.objects.all().select_related('driver__user', 'vehicle', 'category', 'reviewed_by').prefetch_related('attachments')

        if not user.is_admin:
            if hasattr(user, 'driver_profile'):
                queryset = queryset.filter(driver=user.driver_profile)
            else:
                return ExpenseSubmission.objects.none()

        driver_id = self.request.query_params.get('driver')
        if driver_id and user.is_admin:
            queryset = queryset.filter(driver_id=driver_id)

        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        submission_status = self.request.query_params.get('status')
        if submission_status:
            queryset = queryset.filter(status=submission_status)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        driver = None
        if user.is_admin:
            driver_id = self.request.data.get('driver')
            if driver_id:
                driver = Driver.objects.get(id=driver_id)
            elif hasattr(user, 'driver_profile'):
                driver = user.driver_profile
        else:
            if not hasattr(user, 'driver_profile'):
                raise ValidationError("Only registered drivers can submit expenses.")
            driver = user.driver_profile

        vehicle = serializer.validated_data.get('vehicle')
        if not vehicle and driver and driver.assigned_vehicle:
            vehicle = driver.assigned_vehicle

        instance = serializer.save(
            driver=driver,
            vehicle=vehicle,
            status=SubmissionStatus.PENDING
        )

        AuditEvent.objects.create(
            target_model='ExpenseSubmission',
            target_id=instance.id,
            actor=user,
            action='SUBMIT',
            new_status=SubmissionStatus.PENDING,
            notes='Initial expense submission created'
        )

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.status == SubmissionStatus.APPROVED and not self.request.user.is_admin:
            raise ValidationError("Approved expenses cannot be modified.")

        old_status = instance.status
        new_status = old_status

        if not self.request.user.is_admin and old_status == SubmissionStatus.CORRECTION_REQUESTED:
            new_status = SubmissionStatus.PENDING

        updated_instance = serializer.save(status=new_status)

        AuditEvent.objects.create(
            target_model='ExpenseSubmission',
            target_id=updated_instance.id,
            actor=self.request.user,
            action='UPDATE',
            previous_status=old_status,
            new_status=new_status,
            notes='Expense submission details updated'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def approve(self, request, pk=None):
        instance = self.get_object()
        old_status = instance.status
        instance.status = SubmissionStatus.APPROVED
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.rejection_reason = None
        instance.save()

        AuditEvent.objects.create(
            target_model='ExpenseSubmission',
            target_id=instance.id,
            actor=request.user,
            action='APPROVE',
            previous_status=old_status,
            new_status=SubmissionStatus.APPROVED,
            notes=request.data.get('notes', 'Expense approved by admin')
        )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def reject(self, request, pk=None):
        instance = self.get_object()
        reason = request.data.get('reason')
        if not reason:
            return Response({'error': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = instance.status
        instance.status = SubmissionStatus.REJECTED
        instance.rejection_reason = reason
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.save()

        AuditEvent.objects.create(
            target_model='ExpenseSubmission',
            target_id=instance.id,
            actor=request.user,
            action='REJECT',
            previous_status=old_status,
            new_status=SubmissionStatus.REJECTED,
            notes=reason
        )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUserRole])
    @transaction.atomic
    def request_correction(self, request, pk=None):
        instance = self.get_object()
        notes = request.data.get('notes')
        if not notes:
            return Response({'error': 'Correction notes are required.'}, status=status.HTTP_400_BAD_REQUEST)

        old_status = instance.status
        instance.status = SubmissionStatus.CORRECTION_REQUESTED
        instance.correction_notes = notes
        instance.reviewed_by = request.user
        instance.reviewed_at = timezone.now()
        instance.save()

        AuditEvent.objects.create(
            target_model='ExpenseSubmission',
            target_id=instance.id,
            actor=request.user,
            action='REQUEST_CORRECTION',
            previous_status=old_status,
            new_status=SubmissionStatus.CORRECTION_REQUESTED,
            notes=notes
        )
        return Response(self.get_serializer(instance).data)

class AttachmentViewSet(viewsets.ModelViewSet):
    queryset = SubmissionAttachment.objects.all()
    serializer_class = SubmissionAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 5MB)
        if file_obj.size > 5 * 1024 * 1024:
            return Response({'error': 'File size exceeds 5MB limit.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate extension
        allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp', '.pdf']
        extension = '.' + file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else ''
        if extension not in allowed_extensions:
            return Response(
                {'error': f'Unsupported file type {extension}. Allowed types: {", ".join(allowed_extensions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        earnings_id = request.data.get('earnings_submission')
        expense_id = request.data.get('expense_submission')

        earnings_sub = None
        expense_sub = None
        if earnings_id:
            earnings_sub = EarningsSubmission.objects.filter(id=earnings_id).first()
        if expense_id:
            expense_sub = ExpenseSubmission.objects.filter(id=expense_id).first()

        attachment = SubmissionAttachment.objects.create(
            file=file_obj,
            file_name=file_obj.name,
            file_size=file_obj.size,
            file_type=file_obj.content_type or extension,
            earnings_submission=earnings_sub,
            expense_submission=expense_sub
        )

        return Response(self.get_serializer(attachment).data, status=status.HTTP_201_CREATED)
