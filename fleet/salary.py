"""
Driver Salary Management (50% Profit-Sharing Mode).

Single source of truth for salary figures. Nothing here recalculates the 50%
formula: the Driver Salary is the ``driver_share`` already stored on each
eligible ``DailyCalculation`` (= Profit Amount / 2, see ``calculations.py``).

    Total Salary   = SUM(driver_share) over 50% Profit-Sharing daily calculations
    Paid Salary    = SUM(amount) over SalaryPayment rows
    Salary Balance = Total Salary - Paid Salary

Fixed Daily Rent calculations, TourBee Share, CNG, expenses, refunds, wallet
differences and Final GPay amounts are never part of these figures.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.exceptions import APIException, ValidationError

from .calculations import quantize_money
from .models import (
    AuditLog,
    DailyCalculation,
    DriverProfile,
    PaymentMethodChoices,
    PaymentModeChoices,
    SalaryPayment,
)

ZERO = Decimal('0.00')
MIN_PAYMENT = Decimal('0.01')

STATUS_PENDING = 'PENDING'
STATUS_PAID = 'PAID'

# A payment with the same driver, amount, date and reference recorded within
# this window is treated as an accidental double submission (used when the
# client did not send an idempotency key).
DUPLICATE_WINDOW = timedelta(seconds=60)


class DuplicateSalaryPayment(APIException):
    status_code = http_status.HTTP_409_CONFLICT
    default_detail = 'An identical salary payment was just recorded. Duplicate submission blocked.'
    default_code = 'duplicate_salary_payment'


def _money(value):
    return quantize_money(value) if value is not None else ZERO


def salary_status(balance):
    """Pending while anything is outstanding; Paid once the balance is settled."""
    return STATUS_PENDING if balance > ZERO else STATUS_PAID


def eligible_calculations():
    """Only 50% Profit-Sharing daily calculations count towards salary."""
    return DailyCalculation.objects.filter(payment_mode=PaymentModeChoices.REVENUE_SHARING)


def _build_totals(total, paid, days=0, last_payment_date=None):
    total = _money(total)
    paid = _money(paid)
    balance = _money(total - paid)
    return {
        'total_salary': total,
        'paid_salary': paid,
        'salary_balance': balance,
        'status': salary_status(balance),
        'has_salary': total != ZERO or paid != ZERO,
        'days_counted': days,
        'last_payment_date': last_payment_date,
    }


def salary_totals(driver_id):
    """Totals for one driver (all time)."""
    agg = eligible_calculations().filter(driver_id=driver_id).aggregate(
        total=Sum('driver_share'), days=Count('id')
    )
    pay = SalaryPayment.objects.filter(driver_id=driver_id).aggregate(
        paid=Sum('amount'), last=Max('payment_date')
    )
    return _build_totals(agg['total'], pay['paid'], agg['days'] or 0, pay['last'])


def salary_totals_by_driver(driver_ids=None):
    """Totals for many drivers in two grouped queries. Returns {driver_id: totals}."""
    calcs = eligible_calculations()
    pays = SalaryPayment.objects.all()
    if driver_ids is not None:
        calcs = calcs.filter(driver_id__in=driver_ids)
        pays = pays.filter(driver_id__in=driver_ids)

    earned = {
        r['driver_id']: r
        for r in calcs.values('driver_id').annotate(total=Sum('driver_share'), days=Count('id'))
    }
    paid = {
        r['driver_id']: r
        for r in pays.values('driver_id').annotate(paid=Sum('amount'), last=Max('payment_date'))
    }
    out = {}
    for did in set(earned) | set(paid) | set(driver_ids or []):
        e = earned.get(did, {})
        p = paid.get(did, {})
        out[did] = _build_totals(e.get('total'), p.get('paid'), e.get('days', 0), p.get('last'))
    return out


def daily_salary_rows(driver_id, date_from=None, date_to=None):
    """Per-day salary lines (what makes up Total Salary), newest first."""
    qs = eligible_calculations().filter(driver_id=driver_id).select_related('vehicle')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs.order_by('-date', '-created_at')


def _month_start(d):
    return d.replace(day=1)


def _audit(user, action, payment, previous=None):
    AuditLog.objects.create(
        user=user,
        action=action,
        target_model='SalaryPayment',
        target_id=payment.id,
        previous_state=previous,
        new_state={
            'driver': str(payment.driver),
            'amount': str(payment.amount),
            'payment_date': str(payment.payment_date),
            'reference': payment.transaction_reference or '',
        },
    )


def _validate_amount(amount, available):
    if amount is None or amount < MIN_PAYMENT:
        raise ValidationError({'amount': ['Payment amount must be greater than zero.']})
    if amount > available:
        raise ValidationError({
            'amount': [
                f'Payment of ₹{amount:,.2f} exceeds the outstanding salary balance of ₹{max(available, ZERO):,.2f}.'
            ]
        })


@transaction.atomic
def record_salary_payment(
    *,
    driver_id,
    amount,
    payment_date=None,
    recorded_by=None,
    payment_method=None,
    transaction_reference=None,
    notes=None,
    month=None,
    receipt_file=None,
    idempotency_key=None,
):
    """
    Record a salary payment. Returns ``(payment, created)``.

    The driver row is locked (``SELECT ... FOR UPDATE`` on PostgreSQL) before the
    balance is read, so two concurrent payments cannot both pass the balance check.
    """
    # Lock first, then read: serialises payments per driver.
    try:
        driver = DriverProfile.objects.select_for_update().select_related('user').get(pk=driver_id)
    except DriverProfile.DoesNotExist:
        raise ValidationError({'driver': ['Driver not found.']})

    # Idempotent replay: same key => return the original payment, create nothing.
    if idempotency_key:
        existing = SalaryPayment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.driver_id != driver.id:
                raise ValidationError({'idempotency_key': ['This key was already used for another driver.']})
            return existing, False

    amount = _money(amount)
    payment_date = payment_date or timezone.localdate()
    reference = (transaction_reference or '').strip() or None
    notes = (notes or '').strip() or None

    totals = salary_totals(driver.id)
    _validate_amount(amount, totals['salary_balance'])

    if not idempotency_key:
        recent = SalaryPayment.objects.filter(
            driver=driver,
            amount=amount,
            payment_date=payment_date,
            transaction_reference=reference,
            created_at__gte=timezone.now() - DUPLICATE_WINDOW,
        ).exists()
        if recent:
            raise DuplicateSalaryPayment()

    payment = SalaryPayment.objects.create(
        driver=driver,
        month=_month_start(month or payment_date),
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method or PaymentMethodChoices.BANK_TRANSFER,
        transaction_reference=reference,
        notes=notes,
        receipt_file=receipt_file,
        recorded_by=recorded_by,
        idempotency_key=idempotency_key or None,
    )
    _audit(recorded_by, 'CREATE_SALARY_PAYMENT', payment)
    return payment, True


@transaction.atomic
def update_salary_payment(payment_id, *, user, **changes):
    """Edit a payment (admin). The edited amount must still fit inside the driver's salary."""
    payment = SalaryPayment.objects.select_related('driver__user').get(pk=payment_id)
    # Lock the driver row to serialise with concurrent payments.
    DriverProfile.objects.select_for_update().get(pk=payment.driver_id)

    previous = {
        'amount': str(payment.amount),
        'payment_date': str(payment.payment_date),
        'reference': payment.transaction_reference or '',
        'notes': payment.notes or '',
    }

    if 'amount' in changes:
        new_amount = _money(changes['amount'])
        totals = salary_totals(payment.driver_id)
        # Balance as it would be with this payment removed.
        _validate_amount(new_amount, totals['salary_balance'] + payment.amount)
        payment.amount = new_amount
    if 'payment_date' in changes and changes['payment_date']:
        payment.payment_date = changes['payment_date']
        payment.month = _month_start(payment.payment_date)
    if 'transaction_reference' in changes:
        payment.transaction_reference = (changes['transaction_reference'] or '').strip() or None
    if 'notes' in changes:
        payment.notes = (changes['notes'] or '').strip() or None
    if 'payment_method' in changes and changes['payment_method']:
        payment.payment_method = changes['payment_method']

    payment.save()
    _audit(user, 'UPDATE_SALARY_PAYMENT', payment, previous=previous)
    return payment


@transaction.atomic
def delete_salary_payment(payment, *, user):
    DriverProfile.objects.select_for_update().get(pk=payment.driver_id)
    snapshot = {
        'amount': str(payment.amount),
        'payment_date': str(payment.payment_date),
        'reference': payment.transaction_reference or '',
    }
    payment_id = payment.id
    driver_name = str(payment.driver)
    payment.delete()
    AuditLog.objects.create(
        user=user,
        action='DELETE_SALARY_PAYMENT',
        target_model='SalaryPayment',
        target_id=payment_id,
        previous_state={**snapshot, 'driver': driver_name},
    )
