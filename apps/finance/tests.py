from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from datetime import date

from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.submissions.models import (
    ExpenseCategory,
    EarningsSubmission,
    ExpenseSubmission,
    SubmissionStatus
)
from apps.finance.models import SalaryCalculation, RentPayment
from apps.maintenance.models import MaintenanceRecord

User = get_user_model()

class FinancialCalculationsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_fin', email='admin_fin@tourbee.in',
            password='Password123', role=User.Role.ADMIN
        )
        self.user_profit = User.objects.create_user(
            username='drv_profit', email='drv_profit@tourbee.in',
            password='Password123', role=User.Role.DRIVER
        )
        self.user_rent = User.objects.create_user(
            username='drv_rent', email='drv_rent@tourbee.in',
            password='Password123', role=User.Role.DRIVER
        )

        self.vehicle = Vehicle.objects.create(
            registration_number='KL-07-ZZ-9999',
            make='Maruti', model='WagonR CNG', year=2023, daily_rent_rate=Decimal('800.00')
        )
        self.vehicle_rent = Vehicle.objects.create(
            registration_number='KL-07-ZZ-8888',
            make='Hyundai', model='Aura CNG', year=2023, daily_rent_rate=Decimal('800.00')
        )

        self.driver_profit = Driver.objects.create(
            user=self.user_profit, license_number='LIC_PROFIT',
            driver_type=Driver.DriverType.PROFIT_SHARING,
            assigned_vehicle=self.vehicle
        )
        self.driver_rent = Driver.objects.create(
            user=self.user_rent, license_number='LIC_RENT',
            driver_type=Driver.DriverType.DAILY_RENT,
            daily_rent_amount=Decimal('800.00'),
            assigned_vehicle=self.vehicle_rent
        )

        self.cat_cng = ExpenseCategory.objects.create(
            name='CNG Fuel', code='CNG', is_eligible_for_profit_sharing=True
        )
        self.cat_maint = ExpenseCategory.objects.create(
            name='Company Maintenance', code='MAINT', is_eligible_for_profit_sharing=False
        )

    def test_profit_sharing_calculation_accuracy(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)

        # 1. Approved Earnings: Gross 10,000, Commission 2,000, Cash Collected 2,500
        EarningsSubmission.objects.create(
            driver=self.driver_profit,
            vehicle=self.vehicle,
            date=date(2026, 10, 5),
            gross_earnings=Decimal('10000.00'),
            uber_commission=Decimal('2000.00'),
            cash_collected=Decimal('2500.00'),
            status=SubmissionStatus.APPROVED
        )

        # 2. Approved Eligible Expense: CNG 1,600 (Paid by driver out-of-pocket)
        ExpenseSubmission.objects.create(
            driver=self.driver_profit,
            vehicle=self.vehicle,
            category=self.cat_cng,
            date=date(2026, 10, 5),
            amount=Decimal('1600.00'),
            paid_by_driver=True,
            is_operating_expense=True,
            status=SubmissionStatus.APPROVED
        )

        # 3. Excluded Expense: Maintenance 1,200 (Not eligible for profit sharing)
        ExpenseSubmission.objects.create(
            driver=self.driver_profit,
            vehicle=self.vehicle,
            category=self.cat_maint,
            date=date(2026, 10, 5),
            amount=Decimal('1200.00'),
            paid_by_driver=False,
            is_operating_expense=False,
            status=SubmissionStatus.APPROVED
        )

        # 4. Pending Earnings: Gross 3,000 (Should NOT be included)
        EarningsSubmission.objects.create(
            driver=self.driver_profit,
            vehicle=self.vehicle,
            date=date(2026, 10, 6),
            gross_earnings=Decimal('3000.00'),
            uber_commission=Decimal('600.00'),
            status=SubmissionStatus.PENDING
        )

        # Expected Math:
        # Distributable Profit = 10,000 (Gross) - 2,000 (Comm) - 1,600 (CNG) = 6,400
        # Driver 50% = 3,200
        # Company 50% = 3,200
        # Cash Collected Deduction = 2,500
        # Driver Reimbursement = +1,600
        # Net Payable to Driver = 3,200 - 2,500 + 1,600 = 2,300

        resp = client.post('/api/finance/salary-calculations/compute/', {
            'driver_id': self.driver_profit.id,
            'period_start': '2026-10-01',
            'period_end': '2026-10-10',
            'save': True
        })

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = resp.data
        self.assertEqual(Decimal(str(data['total_gross_earnings'])), Decimal('10000.00'))
        self.assertEqual(Decimal(str(data['total_commission'])), Decimal('2000.00'))
        self.assertEqual(Decimal(str(data['total_eligible_expenses'])), Decimal('1600.00'))
        self.assertEqual(Decimal(str(data['distributable_profit'])), Decimal('6400.00'))
        self.assertEqual(Decimal(str(data['driver_share_50'])), Decimal('3200.00'))
        self.assertEqual(Decimal(str(data['company_share_50'])), Decimal('3200.00'))
        self.assertEqual(Decimal(str(data['cash_collected_deduction'])), Decimal('2500.00'))
        self.assertEqual(Decimal(str(data['driver_reimbursements'])), Decimal('1600.00'))
        self.assertEqual(Decimal(str(data['net_payable_to_driver'])), Decimal('2300.00'))

    def test_rent_driver_rejected_from_salary_calculation(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)

        resp = client.post('/api/finance/salary-calculations/compute/', {
            'driver_id': self.driver_rent.id,
            'period_start': '2026-10-01',
            'period_end': '2026-10-10',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('only applicable for profit-sharing', resp.data['error'])
