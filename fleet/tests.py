from decimal import Decimal
from django.test import TestCase
from .calculations import compute_daily_breakdown, compute_fixed_rent

class FormulaCalculationTests(TestCase):
    def test_basic_formula_positive_gpay(self):
        """
        Scenario 1: Driver collects high passenger cash, owes TourBee money via GPay
        A = 5000 (Earnings)
        B = 4000 (Passenger Cash collected)
        E = 1000 (CNG)
        D = 500 (Other Expenses)
        F = 100 (Refund)

        1. Wallet Difference: C = A - B = 5000 - 4000 = 1000.00
        2. Net Profit: G = A - E - D = 5000 - 1000 - 500 = 3500.00
        3. Driver Salary (50%): 3500 / 2 = 1750.00
        4. TourBee Share (50%): 3500 / 2 = 1750.00
        5. Settlement Base: H = TourBee Share = 1750.00
        6. Amount After Wallet: I = 1750 - 1000 = 750.00
        7. Final GPay Amount: J = 750 - 100 = 650.00 (Positive -> Driver pays TourBee)
        """
        res = compute_daily_breakdown(
            total_uber_earnings='5000.00',
            passenger_cash_collected='4000.00',
            expenses='500.00',
            cng_expense='1000.00',
            refund='100.00'
        )
        self.assertEqual(res['wallet_difference'], Decimal('1000.00'))
        self.assertEqual(res['profit_amount'], Decimal('3500.00'))
        self.assertEqual(res['driver_salary'], Decimal('1750.00'))
        self.assertEqual(res['tourbee_share'], Decimal('1750.00'))
        self.assertEqual(res['amount_after_wallet'], Decimal('750.00'))
        self.assertEqual(res['final_gpay_amount'], Decimal('650.00'))

        # Also verify legacy field aliases
        self.assertEqual(res['C'], Decimal('1000.00'))
        self.assertEqual(res['G'], Decimal('3500.00'))
        self.assertEqual(res['driver_share'], Decimal('1750.00'))
        self.assertEqual(res['company_share'], Decimal('1750.00'))
        self.assertEqual(res['H'], Decimal('1750.00'))
        self.assertEqual(res['I'], Decimal('750.00'))
        self.assertEqual(res['J'], Decimal('650.00'))

    def test_negative_gpay_when_company_owes_driver(self):
        """
        Scenario 2: Driver collected low cash, Uber will deposit money to TourBee,
        TourBee owes driver the difference.
        A = 5000 (Earnings)
        B = 2000 (Cash collected)
        E = 1000 (CNG)
        D = 500 (Expenses)
        F = 100 (Refund)

        1. Wallet Difference: C = 5000 - 2000 = 3000.00
        2. Net Profit: G = 5000 - 1000 - 500 = 3500.00
        3. Driver Salary: 1750.00
        4. TourBee Share: 1750.00
        5. Settlement Base: H = 1750.00
        6. Amount After Wallet: I = 1750 - 3000 = -1250.00
        7. Final GPay Amount: J = -1250 - 100 = -1350.00 (Negative -> Company owes driver)
        """
        res = compute_daily_breakdown(
            total_uber_earnings='5000.00',
            passenger_cash_collected='2000.00',
            expenses='500.00',
            cng_expense='1000.00',
            refund='100.00'
        )
        self.assertEqual(res['wallet_difference'], Decimal('3000.00'))
        self.assertEqual(res['profit_amount'], Decimal('3500.00'))
        self.assertEqual(res['driver_salary'], Decimal('1750.00'))
        self.assertEqual(res['tourbee_share'], Decimal('1750.00'))
        self.assertEqual(res['amount_after_wallet'], Decimal('-1250.00'))
        self.assertEqual(res['final_gpay_amount'], Decimal('-1350.00'))
        self.assertEqual(res['J'], Decimal('-1350.00'))

    def test_negative_wallet_difference(self):
        """
        Scenario 3: Driver collected more cash than total Uber earnings (due to tips/adjustments)
        A = 4000
        B = 5000
        C = 4000 - 5000 = -1000 (Negative wallet difference)
        E = 800 (CNG)
        D = 400 (Expenses)
        F = 50 (Refund)

        Net Profit: G = 4000 - 800 - 400 = 2800.00
        TourBee Share: 1400.00
        Amount After Wallet: 1400 - (-1000) = 2400.00
        Final GPay Amount: 2400 - 50 = 2350.00
        """
        res = compute_daily_breakdown(
            total_uber_earnings='4000.00',
            passenger_cash_collected='5000.00',
            expenses='400.00',
            cng_expense='800.00',
            refund='50.00'
        )
        self.assertEqual(res['wallet_difference'], Decimal('-1000.00'))
        self.assertEqual(res['profit_amount'], Decimal('2800.00'))
        self.assertEqual(res['driver_salary'], Decimal('1400.00'))
        self.assertEqual(res['tourbee_share'], Decimal('1400.00'))
        self.assertEqual(res['amount_after_wallet'], Decimal('2400.00'))
        self.assertEqual(res['final_gpay_amount'], Decimal('2350.00'))

    def test_zero_wallet_difference(self):
        """
        Scenario 4: Passenger Cash exactly equals Total Uber Earnings
        A = 3000, B = 3000 => C = 0
        E = 600, D = 300, F = 0
        Net Profit: 3000 - 600 - 300 = 2100.00
        TourBee Share: 1050.00
        Amount After Wallet: 1050 - 0 = 1050.00
        Final GPay Amount: 1050 - 0 = 1050.00
        """
        res = compute_daily_breakdown(
            total_uber_earnings='3000.00',
            passenger_cash_collected='3000.00',
            expenses='300.00',
            cng_expense='600.00',
            refund='0.00'
        )
        self.assertEqual(res['wallet_difference'], Decimal('0.00'))
        self.assertEqual(res['profit_amount'], Decimal('2100.00'))
        self.assertEqual(res['driver_salary'], Decimal('1050.00'))
        self.assertEqual(res['tourbee_share'], Decimal('1050.00'))
        self.assertEqual(res['final_gpay_amount'], Decimal('1050.00'))

    def test_fixed_rent_half_day(self):
        rent = compute_fixed_rent('HALF_DAY')
        self.assertEqual(rent, Decimal('650.00'))

    def test_fixed_rent_full_day(self):
        rent = compute_fixed_rent('FULL_DAY')
        self.assertEqual(rent, Decimal('1200.00'))


class SerializerIdTranslationTests(TestCase):
    """
    Verify that DailyCalculationSerializer.to_internal_value translates
    an apps.drivers.Driver pk / apps.vehicles.Vehicle pk to the
    corresponding fleet.DriverProfile pk / fleet.Vehicle pk, and raises
    a clear 400 when no matching fleet record exists.
    No records are modified; get_or_create is NOT used.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.drivers.models import Driver as AppDriver
        from apps.vehicles.models import Vehicle as AppVehicle
        from fleet.models import DriverProfile, Vehicle as FleetVehicle

        User = get_user_model()

        # Create user + AppDriver. Driver.save() automatically creates a
        # fleet.DriverProfile via its save() hook, so we just fetch it.
        self.user = User.objects.create_user(
            username='test_driver_xlat',
            password='testpass',
            role='DRIVER',
        )
        self.app_driver = AppDriver.objects.create(
            user=self.user,
            driver_type='PROFIT_SHARING',
            license_number='TMP-TEST-XLAT01',
        )
        # Fetch the profile that was auto-created by Driver.save()
        self.fleet_profile = DriverProfile.objects.filter(user=self.user).first()
        if self.fleet_profile is None:
            # Fallback: create manually if the hook is not active in test mode
            self.fleet_profile = DriverProfile.objects.create(
                user=self.user,
                license_number='TMP-TEST-XLAT01',
                payment_mode='REVENUE_SHARING',
            )

        # Create AppVehicle. Vehicle.save() auto-creates the fleet.Vehicle
        # via its save() hook; just fetch it afterwards.
        self.app_vehicle = AppVehicle.objects.create(
            registration_number='KL-99-ZZ-0001',
            make='Test',
            model='Car',
            year=2023,
        )
        self.fleet_vehicle = FleetVehicle.objects.filter(
            registration_number='KL-99-ZZ-0001'
        ).first()
        if self.fleet_vehicle is None:
            self.fleet_vehicle = FleetVehicle.objects.create(
                registration_number='KL-99-ZZ-0001',
                make='Test',
                model='Car',
                year=2023,
                is_active=True,
            )

    def _serializer(self):
        from fleet.serializers import DailyCalculationSerializer
        return DailyCalculationSerializer()

    def test_driver_id_translates_to_fleet_profile(self):
        """
        Sending apps.drivers.Driver.pk should be silently remapped to
        the fleet.DriverProfile.pk for the same user; no 400 should be
        raised for the driver field.
        """
        s = self._serializer()
        data = {'driver': self.app_driver.id}
        try:
            s.to_internal_value(data)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError
            if not isinstance(exc, ValidationError):
                raise
            # Only vehicle/date/etc may be missing — driver must NOT be in errors.
            self.assertNotIn('driver', exc.detail,
                             f"driver field raised unexpected error: {exc.detail.get('driver')}")

    def test_vehicle_id_translates_to_fleet_vehicle(self):
        """
        Sending apps.vehicles.Vehicle.pk should be silently remapped to
        the fleet.Vehicle.pk that shares the same registration_number;
        no 400 should be raised for the vehicle field.
        """
        s = self._serializer()
        data = {'vehicle': self.app_vehicle.id}
        try:
            s.to_internal_value(data)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError
            if not isinstance(exc, ValidationError):
                raise
            # Only other required fields may be missing — vehicle must NOT be in errors.
            self.assertNotIn('vehicle', exc.detail,
                             f"vehicle field raised unexpected error: {exc.detail.get('vehicle')}")

    def test_driver_with_no_fleet_profile_returns_400(self):
        """A driver id that has no matching DriverProfile returns a clear 400."""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        s = self._serializer()
        with self.assertRaises(DRFValidationError) as ctx:
            s.to_internal_value({'driver': 999999})
        self.assertIn('driver', ctx.exception.detail)

    def test_vehicle_with_no_fleet_record_returns_400(self):
        """A vehicle id that has no matching fleet.Vehicle returns a clear 400."""
        from rest_framework.exceptions import ValidationError as DRFValidationError
        s = self._serializer()
        with self.assertRaises(DRFValidationError) as ctx:
            s.to_internal_value({'vehicle': 999999})
        self.assertIn('vehicle', ctx.exception.detail)
