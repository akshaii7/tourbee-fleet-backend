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
    50% TourBee Profit-Sharing Calculation (Corrected):

    Step 1: Wallet Difference = Total Uber Earnings - Passenger Cash Collected
        (Amount Uber settled directly to company wallet; positive = Uber paid company)

    Step 2: Net Profit = Total Uber Earnings - CNG Expense - Other Expenses

    Step 3: Driver Share = Net Profit × 50%

    Step 4: TourBee Share = Net Profit × 50%

    Step 5: Final GPay Amount = TourBee Share - Wallet Difference - Refund
        (What the driver must pay TourBee via GPay)
        - TourBee is owed their 50% share
        - Wallet Difference was already settled by Uber to TourBee, so subtract it
        - Refund reduces what the driver owes
        - If negative, company owes the driver

    Test Example:
    Total Uber Earnings: ₹13,667
    Passenger Cash Collected: ₹13,210
    CNG Expense: ₹4,825
    Other Expenses: ₹826
    Refund: ₹415

    Expected:
    Wallet Difference: ₹457
    Net Profit: ₹8,016
    Driver Share: ₹4,008
    TourBee Share: ₹4,008
    Final GPay = 4,008 - 457 - 415 = ₹3,136
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

    # Step 5: Final GPay Amount = TourBee Share - Wallet Difference - Refund
    # TourBee is owed their 50%, but Uber already settled wallet_difference
    # to the company, and refund reduces the amount owed.
    amount_after_wallet = quantize_money(tourbee_share - wallet_difference)
    final_gpay_amount = quantize_money(amount_after_wallet - F)
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
        'amount_after_wallet': amount_after_wallet,
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
        'H': tourbee_share,           # H = TourBee's 50% share (settlement base)
        'I': amount_after_wallet,      # I = TourBee Share - Wallet Difference
        'J': J,                        # J = Final GPay Amount
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


