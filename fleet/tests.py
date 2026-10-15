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
