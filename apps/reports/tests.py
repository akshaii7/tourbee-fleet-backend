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

User = get_user_model()

class ReportsAndExportsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_rep', email='rep@tourbee.in',
            password='Password123', role=User.Role.ADMIN
        )
        self.driver_user = User.objects.create_user(
            username='driver_rep', email='drep@tourbee.in',
            password='Password123', role=User.Role.DRIVER
        )
        self.veh = Vehicle.objects.create(
            registration_number='KL-07-AB-1234',
            make='Maruti', model='WagonR CNG', year=2023
        )
        self.driver = Driver.objects.create(
            user=self.driver_user, license_number='LIC_REP',
            driver_type=Driver.DriverType.PROFIT_SHARING,
            assigned_vehicle=self.veh
        )
        self.cat_cng = ExpenseCategory.objects.create(
            name='CNG Fuel', code='CNG', is_eligible_for_profit_sharing=True
        )

        EarningsSubmission.objects.create(
            driver=self.driver, vehicle=self.veh,
            date=date(2026, 10, 8), gross_earnings=Decimal('3200.00'),
            uber_commission=Decimal('640.00'), status=SubmissionStatus.APPROVED
        )

    def test_dashboard_summary_admin(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.get('/api/reports/dashboard/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['role'], 'ADMIN')
        self.assertIn('overview', resp.data)
        self.assertIn('financials_month', resp.data)

    def test_financial_reports_admin(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.get('/api/reports/financial/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('period', resp.data)
        self.assertIn('summary', resp.data)
        self.assertIn('vehicle_breakdown', resp.data)
        self.assertIn('driver_breakdown', resp.data)
        summary = resp.data['summary']
        self.assertEqual(summary['gross_uber_earnings'], 3200.0)
        self.assertEqual(summary['uber_commission'], 640.0)
        self.assertEqual(summary['total_trips'], 0)
        self.assertTrue(len(resp.data['vehicle_breakdown']) >= 1)
        self.assertTrue(len(resp.data['driver_breakdown']) >= 1)

    def test_export_earnings_csv_and_excel(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)

        # CSV export
        resp_csv = client.get('/api/reports/export/?type=earnings&format=csv')
        self.assertEqual(resp_csv.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_csv['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn(b'Gross Uber Earnings', resp_csv.content)

        # Excel export
        resp_excel = client.get('/api/reports/export/?type=earnings&format=excel')
        self.assertEqual(resp_excel.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp_excel['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
