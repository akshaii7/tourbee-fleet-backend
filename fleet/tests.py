from decimal import Decimal
from django.test import TestCase
from .calculations import compute_daily_breakdown

class FormulaCalculationTests(TestCase):
    def test_basic_formula_positive_wallet(self):
        """
        Scenario 1:
        A = 5000 (Earnings)
        B = 3000 (Cash collected)
        C = A - B = 2000 (Wallet > 0)
        D = 500 (Uber charge)
        E = 1000 (CNG)
        F = 100 (Refund)
        
        G = A - D - E = 5000 - 500 - 1000 = 3500
        Driver Share = 3500 / 2 = 1750
        Company Share = 3500 / 2 = 1750
        H = G + D = 3500 + 500 = 4000
        I = H - F = 4000 - 100 = 3900
        Wallet C > 0: J = I - C = 3900 - 2000 = 1900
        (Also verified: J = A - E - F - abs(C) = 5000 - 1000 - 100 - 2000 = 1900)
        """
        res = compute_daily_breakdown(
            a='5000.00',
            b='3000.00',
            d='500.00',
            e='1000.00',
            f='100.00'
        )
        self.assertEqual(res['C'], Decimal('2000.00'))
        self.assertEqual(res['G'], Decimal('3500.00'))
        self.assertEqual(res['driver_share'], Decimal('1750.00'))
        self.assertEqual(res['company_share'], Decimal('1750.00'))
        self.assertEqual(res['H'], Decimal('4000.00'))
        self.assertEqual(res['I'], Decimal('3900.00'))
        self.assertEqual(res['J'], Decimal('1900.00'))

    def test_negative_wallet_when_cash_exceeds_earnings(self):
        """
        Scenario 2:
        A = 4000
        B = 5000 (Cash collected > earnings)
        C = 4000 - 5000 = -1000 (Wallet < 0)
        D = 400
        E = 800
        F = 50

        G = 4000 - 400 - 800 = 2800
        Driver Share = 1400
        Company Share = 1400
        H = 2800 + 400 = 3200
        I = 3200 - 50 = 3150
        When C < 0:
        J = I + C = 3150 + (-1000) = 2150
        (Also verified: J = I - abs(C) = 3150 - 1000 = 2150)
        """
        res = compute_daily_breakdown(
            a='4000.00',
            b='5000.00',
            d='400.00',
            e='800.00',
            f='50.00'
        )
        self.assertEqual(res['C'], Decimal('-1000.00'))
        self.assertEqual(res['G'], Decimal('2800.00'))
        self.assertEqual(res['driver_share'], Decimal('1400.00'))
        self.assertEqual(res['company_share'], Decimal('1400.00'))
        self.assertEqual(res['H'], Decimal('3200.00'))
        self.assertEqual(res['I'], Decimal('3150.00'))
        self.assertEqual(res['J'], Decimal('2150.00'))

    def test_zero_wallet(self):
        """
        Scenario 3:
        A = 3000, B = 3000 => C = 0
        D = 300, E = 600, F = 0
        G = 3000 - 300 - 600 = 2100
        Driver Share = 1050
        H = 2100 + 300 = 2400
        I = 2400 - 0 = 2400
        C == 0: J = I = 2400
        """
        res = compute_daily_breakdown(
            a='3000.00',
            b='3000.00',
            d='300.00',
            e='600.00',
            f='0.00'
        )
        self.assertEqual(res['C'], Decimal('0.00'))
        self.assertEqual(res['G'], Decimal('2100.00'))
        self.assertEqual(res['driver_share'], Decimal('1050.00'))
        self.assertEqual(res['company_share'], Decimal('1050.00'))
        self.assertEqual(res['H'], Decimal('2400.00'))
        self.assertEqual(res['I'], Decimal('2400.00'))
        self.assertEqual(res['J'], Decimal('2400.00'))

    def test_negative_j_handled_and_visible(self):
        """
        Scenario 4: High expenses/refund yielding negative J
        A = 1000, B = 500 (C = 500)
        D = 200, E = 800, F = 300
        G = 1000 - 200 - 800 = 0
        Driver Share = 0
        H = 0 + 200 = 200
        I = 200 - 300 = -100
        C > 0: J = -100 - 500 = -600
        """
        res = compute_daily_breakdown(
            a='1000.00',
            b='500.00',
            d='200.00',
            e='800.00',
            f='300.00'
        )
        self.assertEqual(res['J'], Decimal('-600.00'))
        self.assertTrue(res['J'] < Decimal('0'))

    def test_fixed_rent_half_day(self):
        from .calculations import compute_fixed_rent
        rent = compute_fixed_rent('HALF_DAY')
        self.assertEqual(rent, Decimal('650.00'))

    def test_fixed_rent_full_day(self):
        from .calculations import compute_fixed_rent
        rent = compute_fixed_rent('FULL_DAY')
        self.assertEqual(rent, Decimal('1200.00'))

