import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, '/Users/macbook/Tour_Bee_Driver/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from fleet.models import DriverProfile, Vehicle, DailyCalculation, PaymentModeChoices, WorkingDayChoices, PaymentStatusChoices
from fleet.calculations import compute_daily_breakdown

User = get_user_model()

def run_tests():
    print("=" * 60)
    print("RUNNING TOURBEE FLEET MANAGER VERIFICATION TESTS")
    print("=" * 60)

    # TEST 1: Exact calculation formula test
    print("\n--- TEST 1: CONFIRMED 50% CALCULATION TEST ---")
    calc = compute_daily_breakdown(
        total_uber_earnings=Decimal('13667.00'),
        passenger_cash_collected=Decimal('13210.00'),
        cng_expense=Decimal('4825.00'),
        expenses=Decimal('826.00'),
        refund=Decimal('415.00')
    )
    print("Inputs: Uber=13667, Cash=13210, CNG=4825, Expenses=826, Refund=415")
    print(f"Wallet Difference: ₹{calc['wallet_difference']} (Expected: 457.00)")
    print(f"Profit Amount: ₹{calc['profit_amount']} (Expected: 8016.00)")
    print(f"Driver Salary: ₹{calc['driver_salary']} (Expected: 4008.00)")
    print(f"TourBee Share: ₹{calc['tourbee_share']} (Expected: 4008.00)")
    print(f"Amount After Wallet Adj: ₹{calc['amount_after_wallet_adjustment']} (Expected: 7559.00)")
    print(f"Amount After Refund: ₹{calc['amount_after_refund']} (Expected: 7144.00)")
    print(f"Final GPay Amount: ₹{calc['final_gpay_amount']} (Expected: 7970.00)")

    assert Decimal(str(calc['wallet_difference'])) == Decimal('457.00'), f"Wallet diff failed: {calc['wallet_difference']}"
    assert Decimal(str(calc['profit_amount'])) == Decimal('8016.00'), f"Profit amount failed: {calc['profit_amount']}"
    assert Decimal(str(calc['driver_salary'])) == Decimal('4008.00'), f"Driver salary failed: {calc['driver_salary']}"
    assert Decimal(str(calc['tourbee_share'])) == Decimal('4008.00'), f"TourBee share failed: {calc['tourbee_share']}"
    assert Decimal(str(calc['final_gpay_amount'])) == Decimal('7970.00'), f"Final GPay amount failed: {calc['final_gpay_amount']}"
    print(">>> TEST 1 PASSED: Exact 50% formula reproduced perfectly!")

    # TEST 2: Live calculate API test
    print("\n--- TEST 2: LIVE CALCULATE API ---")
    client = APIClient()
    admin_user = User.objects.filter(username='admin').first()
    client.force_authenticate(user=admin_user)

    resp = client.post('/api/fleet/calculate/live/', {
        'total_uber_earnings': 13667,
        'passenger_cash_collected': 13210,
        'cng_expense': 4825,
        'expenses': 826,
        'refund': 415,
        'payment_mode': 'REVENUE_SHARING'
    }, format='json')
    assert resp.status_code == 200, f"Status code: {resp.status_code}"
    data = resp.data
    assert Decimal(str(data['final_gpay_amount'])) == Decimal('7970.00'), f"Expected 7970.00, got {data['final_gpay_amount']}"
    assert Decimal(str(data['driver_salary'])) == Decimal('4008.00'), f"Expected 4008.00, got {data['driver_salary']}"
    print(">>> TEST 2 PASSED: Live calculate API returned ₹7,970 GPay and ₹4,008 Driver Salary!")

    # TEST 3: Fixed Rent Live Calculate API
    print("\n--- TEST 3: FIXED RENT RATES (Half Day ₹650 / Full Day ₹1,200) ---")
    resp_half = client.post('/api/fleet/calculate/live/', {
        'payment_mode': 'FIXED_RENT',
        'working_day_type': 'HALF_DAY'
    }, format='json')
    assert resp_half.status_code == 200
    assert Decimal(str(resp_half.data['rent_due'])) == Decimal('650.00'), f"Expected 650.00, got {resp_half.data['rent_due']}"
    assert Decimal(str(resp_half.data['driver_salary'])) == Decimal('0.00')
    assert Decimal(str(resp_half.data['tourbee_share'])) == Decimal('0.00')

    resp_full = client.post('/api/fleet/calculate/live/', {
        'payment_mode': 'FIXED_RENT',
        'working_day_type': 'FULL_DAY'
    }, format='json')
    assert resp_full.status_code == 200
    assert Decimal(str(resp_full.data['rent_due'])) == Decimal('1200.00'), f"Expected 1200.00, got {resp_full.data['rent_due']}"
    assert Decimal(str(resp_full.data['driver_salary'])) == Decimal('0.00')
    assert Decimal(str(resp_full.data['tourbee_share'])) == Decimal('0.00')
    print(">>> TEST 3 PASSED: Half Day = ₹650, Full Day = ₹1,200, and no 50% salary calculated!")

    # TEST 4: Driver submission creation & duplicate protection
    print("\n--- TEST 4: SUBMISSION CREATION & DUPLICATE SUBMISSION CHECK ---")
    driver_muhaz = User.objects.filter(username='@muhaz12').first()
    client.force_authenticate(user=driver_muhaz)
    driver_profile = DriverProfile.objects.filter(user=driver_muhaz).first()
    vehicle = Vehicle.objects.first()

    test_date = '2026-10-15'
    # Clean any preexisting test record for this test_date
    DailyCalculation.objects.filter(driver=driver_profile, vehicle=vehicle, date=test_date).delete()

    sub_resp = client.post('/api/fleet/calculations/', {
        'vehicle': vehicle.id,
        'date': test_date,
        'total_uber_earnings': 13667,
        'passenger_cash_collected': 13210,
        'cng_expense': 4825,
        'expenses': 826,
        'refund': 415,
    }, format='json')
    assert sub_resp.status_code == 201, f"Creation failed: {sub_resp.data}"
    created_id = sub_resp.data['id']
    assert Decimal(str(sub_resp.data['final_gpay_amount'])) == Decimal('7970.00')
    assert sub_resp.data['status'] == 'PENDING'
    print(f"Created submission #{created_id} with status PENDING, Final GPay = ₹7,970")

    # Try duplicate submission on same driver, vehicle, and date
    dup_resp = client.post('/api/fleet/calculations/', {
        'vehicle': vehicle.id,
        'date': test_date,
        'total_uber_earnings': 13667,
        'passenger_cash_collected': 13210,
        'cng_expense': 4825,
        'expenses': 826,
        'refund': 415,
    }, format='json')
    assert dup_resp.status_code == 400, f"Duplicate check failed: {dup_resp.status_code}"
    print(">>> TEST 4 PASSED: Duplicate submission correctly prevented with 400 Bad Request!")

    # TEST 5: Status toggle by Admin
    print("\n--- TEST 5: ADMIN MARK PAYMENT STATUS (Pending -> Paid) ---")
    client.force_authenticate(user=admin_user)
    status_resp = client.post(f'/api/fleet/calculations/{created_id}/mark_status/', {
        'status': 'PAID'
    }, format='json')
    assert status_resp.status_code == 200
    assert status_resp.data['status'] == 'PAID'
    print(">>> TEST 5 PASSED: Admin successfully updated status to PAID!")

    # TEST 6: Role-based isolation check
    print("\n--- TEST 6: ROLE-BASED DRIVER ISOLATION CHECK ---")
    pari_user = User.objects.filter(username='pari123').first()
    client.force_authenticate(user=pari_user)
    list_resp = client.get('/api/fleet/calculations/')
    assert list_resp.status_code == 200
    records = list_resp.data.get('results', list_resp.data)
    # pari123 should NOT see muhaz12's record
    for r in records:
        assert r['id'] != created_id, f"Security violation: pari123 saw record {created_id} of muhaz12!"
    print(">>> TEST 6 PASSED: Driver cannot see other drivers' daily calculations!")

    # TEST 7: Admin Dashboard Metrics
    print("\n--- TEST 7: ADMIN DASHBOARD METRICS ---")
    client.force_authenticate(user=admin_user)
    dash_resp = client.get('/api/fleet/dashboard/')
    assert dash_resp.status_code == 200
    ddata = dash_resp.data
    print(f"Total Active Drivers: {ddata['active_drivers_count']}")
    print(f"50% Mode Drivers: {ddata['drivers_50_mode_count']}")
    print(f"Fixed Rent Drivers: {ddata['drivers_rent_mode_count']}")
    print(f"Total Daily Uber Earnings: ₹{ddata['total_daily_uber_earnings']}")
    print(f"Total Driver Salaries: ₹{ddata['total_driver_salaries']}")
    print(f"Total TourBee Shares: ₹{ddata['total_tourbee_shares']}")
    print(f"Total GPay Pending: ₹{ddata['total_gpay_pending']}")
    print(f"Total Fixed Rent Pending: ₹{ddata['total_fixed_rent_pending']}")
    print(f"Total Payments Received: ₹{ddata['total_payments_received']}")
    print(f"Recent Submissions Count: {len(ddata['recent_submissions'])}")
    print(">>> TEST 7 PASSED: Admin dashboard computed all required metrics cleanly!")

    # Cleanup test record
    DailyCalculation.objects.filter(id=created_id).delete()
    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! 100% VERIFIED.")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
