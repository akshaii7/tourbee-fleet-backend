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
    AuditEvent,
    SubmissionStatus
)

User = get_user_model()

class SubmissionsWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin_sub', email='admin_sub@tourbee.in',
            password='Password123', role=User.Role.ADMIN
        )
        self.user1 = User.objects.create_user(
            username='driver1', email='driver1@tourbee.in',
            password='Password123', role=User.Role.DRIVER
        )
        self.user2 = User.objects.create_user(
            username='driver2', email='driver2@tourbee.in',
            password='Password123', role=User.Role.DRIVER
        )

        self.vehicle1 = Vehicle.objects.create(
            registration_number='KL-07-XX-1111',
            make='Maruti', model='WagonR CNG', year=2023
        )
        self.vehicle2 = Vehicle.objects.create(
            registration_number='KL-07-XX-2222',
            make='Maruti', model='Dzire CNG', year=2024
        )

        self.driver1 = Driver.objects.create(
            user=self.user1, license_number='LIC1111',
            driver_type=Driver.DriverType.PROFIT_SHARING,
            assigned_vehicle=self.vehicle1
        )
        self.driver2 = Driver.objects.create(
            user=self.user2, license_number='LIC2222',
            driver_type=Driver.DriverType.DAILY_RENT,
            assigned_vehicle=self.vehicle2
        )

        self.cat_cng = ExpenseCategory.objects.create(
            name='CNG Fuel', code='CNG', is_eligible_for_profit_sharing=True
        )

    def test_earnings_submission_initial_pending_and_audit(self):
        client = APIClient()
        client.force_authenticate(user=self.user1)

        payload = {
            'vehicle': self.vehicle1.id,
            'date': '2026-10-10',
            'online_hours': '8.5',
            'trips_count': 12,
            'gross_earnings': '3500.00',
            'cash_collected': '800.00',
            'uber_commission': '700.00',
            'notes': 'Normal shift'
        }
        response = client.post('/api/submissions/earnings/', payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['status'], SubmissionStatus.PENDING)

        submission_id = response.data['id']
        sub = EarningsSubmission.objects.get(id=submission_id)
        self.assertEqual(sub.status, SubmissionStatus.PENDING)
        self.assertEqual(sub.driver, self.driver1)

        # Audit Event check
        audit = AuditEvent.objects.filter(target_model='EarningsSubmission', target_id=sub.id).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, 'SUBMIT')

    def test_driver_isolation_security(self):
        # Driver 1 creates submission
        sub = EarningsSubmission.objects.create(
            driver=self.driver1,
            vehicle=self.vehicle1,
            date=date(2026, 10, 1),
            gross_earnings=Decimal('3000.00'),
            uber_commission=Decimal('600.00'),
            status=SubmissionStatus.PENDING
        )

        # Driver 2 tries to access Driver 1's submission
        client = APIClient()
        client.force_authenticate(user=self.user2)
        response = client.get('/api/submissions/earnings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in response.data['results']]
        self.assertNotIn(sub.id, ids)

    def test_admin_approval_and_rejection_workflow(self):
        sub = EarningsSubmission.objects.create(
            driver=self.driver1,
            vehicle=self.vehicle1,
            date=date(2026, 10, 2),
            gross_earnings=Decimal('4000.00'),
            uber_commission=Decimal('800.00'),
            status=SubmissionStatus.PENDING
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=self.admin)

        # Approve
        resp_approve = admin_client.post(f'/api/submissions/earnings/{sub.id}/approve/')
        self.assertEqual(resp_approve.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.status, SubmissionStatus.APPROVED)
        self.assertEqual(sub.reviewed_by, self.admin)

        # Reject another
        sub2 = EarningsSubmission.objects.create(
            driver=self.driver1,
            vehicle=self.vehicle1,
            date=date(2026, 10, 3),
            gross_earnings=Decimal('2000.00'),
            uber_commission=Decimal('400.00'),
            status=SubmissionStatus.PENDING
        )
        resp_reject = admin_client.post(f'/api/submissions/earnings/{sub2.id}/reject/', {
            'reason': 'Receipt blurred and illegible'
        })
        self.assertEqual(resp_reject.status_code, status.HTTP_200_OK)
        sub2.refresh_from_db()
        self.assertEqual(sub2.status, SubmissionStatus.REJECTED)
        self.assertEqual(sub2.rejection_reason, 'Receipt blurred and illegible')
