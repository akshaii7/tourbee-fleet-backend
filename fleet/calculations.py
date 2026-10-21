from decimal import Decimal, ROUND_HALF_UP

TWO_PLACES = Decimal('0.01')

def to_decimal(val) -> Decimal:
    if val is None or val == '':
        return Decimal('0.00')
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal('0.00')

def quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

def compute_daily_breakdown(
    total_uber_earnings,
    passenger_cash_collected,
    expenses,
    cng_expense,
    refund
):
    """
    Confirmed 50% TourBee Profit-Sharing Calculation:

    Step 1:
    Wallet Difference = Total Uber Earnings - Passenger Cash Collected

    Step 2:
    Profit Amount = Total Uber Earnings - CNG Expense - Expenses

    Step 3:
    Driver Salary = Profit Amount / 2

    Step 4:
    TourBee Share = Profit Amount / 2

    Step 5:
    Initial Settlement Amount = Profit Amount

    Step 6:
    Amount After Wallet Adjustment = Initial Settlement Amount - Wallet Difference

    Step 7:
    Amount After Refund = Amount After Wallet Adjustment - Refund

    Step 8:
    Final GPay Amount = Amount After Refund + Expenses

    Equivalent formula:
    Final GPay Amount = Profit Amount - Wallet Difference - Refund + Expenses

    Test Example:
    Total Uber Earnings: ₹13,667
    Passenger Cash Collected: ₹13,210
    CNG Expense: ₹4,825
    Expenses: ₹826
    Refund: ₹415

    Expected:
    Wallet Difference: ₹457
    Profit Amount: ₹8,016
    Driver Salary: ₹4,008
    TourBee Share: ₹4,008
    Amount After Wallet Adjustment: ₹7,559
    Amount After Refund: ₹7,144
    Final GPay Amount: ₹7,970
    """
    A = quantize_money(to_decimal(total_uber_earnings))
    B = quantize_money(to_decimal(passenger_cash_collected))
    D = quantize_money(to_decimal(expenses))
    E = quantize_money(to_decimal(cng_expense))
    F = quantize_money(to_decimal(refund))

    # Step 1: Wallet Difference = Total Uber Earnings - Passenger Cash Collected
    wallet_difference = quantize_money(A - B)
    C = wallet_difference

    # Step 2: Net Profit = Total Uber Earnings - CNG Expense - Expenses
    profit_amount = quantize_money(A - E - D)
    G = profit_amount

    # Step 3: Driver Share = Net Profit / 2
    driver_salary = quantize_money(profit_amount / Decimal('2'))

    # Step 4: TourBee Share = Net Profit / 2
    tourbee_share = quantize_money(profit_amount / Decimal('2'))

    # Step 5: Initial Settlement Amount = Profit Amount
    initial_settlement_amount = profit_amount

    # Step 6: Amount After Wallet Adjustment = Initial Settlement Amount - Wallet Difference
    amount_after_wallet_adjustment = quantize_money(initial_settlement_amount - wallet_difference)

    # Step 7: Amount After Refund = Amount After Wallet Adjustment - Refund
    amount_after_refund = quantize_money(amount_after_wallet_adjustment - F)

    # Step 8: Final GPay Amount = Amount After Refund + Expenses
    final_gpay_amount = quantize_money(amount_after_refund + D)
    J = final_gpay_amount

    return {
        # Named breakdown fields
        'total_uber_earnings': A,
        'passenger_cash_collected': B,
        'wallet_difference': wallet_difference,
        'cng_expense': E,
        'expenses': D,
        'refund': F,
        'profit_amount': profit_amount,
        'driver_salary': driver_salary,
        'tourbee_share': tourbee_share,
        'initial_settlement_amount': initial_settlement_amount,
        'amount_after_wallet_adjustment': amount_after_wallet_adjustment,
        'amount_after_wallet': amount_after_wallet_adjustment,
        'amount_after_refund': amount_after_refund,
        'final_gpay_amount': final_gpay_amount,

        # Legacy aliases for model fields (H, I, J)
        'A': A,
        'B': B,
        'C': C,
        'D': D,
        'E': E,
        'F': F,
        'G': G,
        'driver_share': driver_salary,
        'company_share': tourbee_share,
        'H': initial_settlement_amount,
        'I': amount_after_refund,
        'J': J,
    }

HALF_DAY_RENT = Decimal('650.00')
FULL_DAY_RENT = Decimal('1200.00')

def compute_fixed_rent(working_day_type: str) -> Decimal:
    """
    Fixed Rent Mode:
    Half Day = ₹650
    Full Day = ₹1,200
    """
    if str(working_day_type).upper() == 'HALF_DAY':
        return HALF_DAY_RENT
    return FULL_DAY_RENT


