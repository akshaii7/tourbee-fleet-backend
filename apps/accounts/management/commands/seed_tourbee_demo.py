from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.submissions.models import (
    ExpenseCategory,
    EarningsSubmission,
    ExpenseSubmission,
    AuditEvent,
    SubmissionStatus
)
from apps.finance.models import (
    BusinessSettings,
    SalaryCalculation,
    SalaryPayment,
    RentPayment,
    CalculationStatus,
    PaymentMethod
)
from apps.maintenance.models import MaintenanceRecord, MaintenanceType

User = get_user_model()

class Command(BaseCommand):
    help = "Seed realistic demo data for TourBee Fleet Manager (Kerala, India)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding TourBee Fleet Manager database..."))

        # 1. Business Settings
        settings_obj = BusinessSettings.get_settings()
        settings_obj.company_name = "TourBee Kerala Fleet Pvt Ltd"
        settings_obj.currency = "INR"
        settings_obj.currency_symbol = "₹"
        settings_obj.timezone = "Asia/Kolkata"
        settings_obj.default_driver_profit_share_pct = Decimal("50.00")
        settings_obj.default_company_profit_share_pct = Decimal("50.00")
        settings_obj.default_daily_rent = Decimal("850.00")
        settings_obj.contact_phone = "+91 98470 44211"
        settings_obj.contact_email = "fleet.admin@tourbee.in"
        settings_obj.address = "Door No. 34/1102, MG Road, Ernakulam, Kochi, Kerala - 682016"
        settings_obj.save()
        self.stdout.write(self.style.SUCCESS("✓ Business Settings configured."))

        # 2. Expense Categories
        categories_data = [
            ("CNG Fuel", "CNG", True, "CNG gas station refills in Kerala (Edappally, Palarivattom, Kundannoor)"),
            ("Toll / FASTag", "TOLL", True, "Kerala Highway Tolls (Kumbalam, Paliyekkara, Airport Expressway)"),
            ("Vehicle Wash & Sanitization", "WASH", True, "Weekly pressure wash and cabin interior cleaning"),
            ("Tyre Puncture & Air Check", "PUNCTURE", True, "Wheel puncture repair and nitrogen inflation"),
            ("Parking Charges", "PARKING", True, "Railway station, Airport, Mall parking receipts"),
            ("Minor Consumables", "MINOR_EXPENSE", True, "Windshield wiper fluid, fuse, bulb replacement"),
            ("Major Workshop Service", "MAINT_SERVICE", False, "Excluded from driver profit sharing - Company overhead"),
            ("Accident Bodywork", "MAINT_BODY", False, "Insurance excess and dent repair - Company overhead"),
        ]

        cat_objs = {}
        for name, code, is_eligible, desc in categories_data:
            cat, _ = ExpenseCategory.objects.get_or_create(
                code=code,
                defaults={'name': name, 'is_eligible_for_profit_sharing': is_eligible, 'description': desc}
            )
            cat_objs[code] = cat
        self.stdout.write(self.style.SUCCESS("✓ Expense categories initialized."))

        # 3. Create Admin User
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={
                'email': 'admin@tourbee.in',
                'first_name': 'Vishnu',
                'last_name': 'Nambiar',
                'role': User.Role.ADMIN,
                'phone_number': '+91 98470 11223',
                'city': 'Kochi',
                'state': 'Kerala',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.email = 'admin@tourbee.in'
        admin_user.set_password("TourBee@2026")
        admin_user.save()
        self.stdout.write(self.style.SUCCESS(f"✓ Admin account: {admin_user.username} (Password: TourBee@2026)"))

        # 4. Create Fleet Vehicles
        today = timezone.localdate()
        vehicles_data = [
            {
                'reg': 'KL-07-CJ-4521', 'make': 'Maruti Suzuki', 'model': 'WagonR LXi CNG', 'year': 2023,
                'fuel': Vehicle.FuelType.CNG, 'status': Vehicle.Status.ACTIVE, 'odometer': 38450,
                'ins_exp': today + timedelta(days=120), 'fit_exp': today + timedelta(days=240), 'rent_rate': Decimal('800.00')
            },
            {
                'reg': 'KL-07-DE-8924', 'make': 'Maruti Suzuki', 'model': 'Dzire Tour S CNG', 'year': 2024,
                'fuel': Vehicle.FuelType.CNG, 'status': Vehicle.Status.ACTIVE, 'odometer': 21200,
                'ins_exp': today + timedelta(days=210), 'fit_exp': today + timedelta(days=365), 'rent_rate': Decimal('900.00')
            },
            {
                'reg': 'KL-07-DF-6132', 'make': 'Hyundai', 'model': 'Aura Prime CNG', 'year': 2023,
                'fuel': Vehicle.FuelType.CNG, 'status': Vehicle.Status.ACTIVE, 'odometer': 42100,
                'ins_exp': today + timedelta(days=12), 'fit_exp': today + timedelta(days=180), 'rent_rate': Decimal('850.00') # Expiring soon!
            },
            {
                'reg': 'KL-07-EC-1098', 'make': 'Tata Motors', 'model': 'Tigor EV X-Press', 'year': 2024,
                'fuel': Vehicle.FuelType.EV, 'status': Vehicle.Status.ACTIVE, 'odometer': 15800,
                'ins_exp': today + timedelta(days=300), 'fit_exp': today + timedelta(days=400), 'rent_rate': Decimal('950.00')
            },
            {
                'reg': 'KL-07-CJ-9811', 'make': 'Maruti Suzuki', 'model': 'WagonR VXi CNG', 'year': 2022,
                'fuel': Vehicle.FuelType.CNG, 'status': Vehicle.Status.ACTIVE, 'odometer': 59200,
                'ins_exp': today - timedelta(days=3), 'fit_exp': today + timedelta(days=60), 'rent_rate': Decimal('800.00') # Expired alert!
            },
            {
                'reg': 'KL-07-BG-3320', 'make': 'Maruti Suzuki', 'model': 'Ertiga Tour M CNG', 'year': 2023,
                'fuel': Vehicle.FuelType.CNG, 'status': Vehicle.Status.MAINTENANCE, 'odometer': 51000,
                'ins_exp': today + timedelta(days=90), 'fit_exp': today + timedelta(days=150), 'rent_rate': Decimal('1200.00')
            },
        ]

        vehicle_map = {}
        for vd in vehicles_data:
            veh, _ = Vehicle.objects.get_or_create(
                registration_number=vd['reg'],
                defaults={
                    'make': vd['make'],
                    'model': vd['model'],
                    'year': vd['year'],
                    'fuel_type': vd['fuel'],
                    'status': vd['status'],
                    'current_odometer': vd['odometer'],
                    'insurance_expiry': vd['ins_exp'],
                    'fitness_expiry': vd['fit_exp'],
                    'daily_rent_rate': vd['rent_rate'],
                    'insurance_policy_no': f"NIC-POL-{random.randint(100000, 999999)}",
                    'rc_number': f"KL07{random.randint(10000000, 99999999)}",
                }
            )
            vehicle_map[vd['reg']] = veh
        self.stdout.write(self.style.SUCCESS("✓ Fleet vehicles created with real Kerala registrations."))

        # 5. Create Drivers
        drivers_info = [
            {
                'username': 'rahul_k', 'email': 'rahul.k@tourbee.in', 'first_name': 'Rahul', 'last_name': 'Krishnan',
                'phone': '+91 98471 22334', 'type': Driver.DriverType.PROFIT_SHARING, 'license': 'KL0720180045211',
                'vehicle': vehicle_map['KL-07-CJ-4521'], 'daily_rent': Decimal('0.00')
            },
            {
                'username': 'anoop_m', 'email': 'anoop.m@tourbee.in', 'first_name': 'Anoop', 'last_name': 'Menon',
                'phone': '+91 98472 33445', 'type': Driver.DriverType.PROFIT_SHARING, 'license': 'KL0720190089123',
                'vehicle': vehicle_map['KL-07-DE-8924'], 'daily_rent': Decimal('0.00')
            },
            {
                'username': 'faisal_k', 'email': 'faisal.k@tourbee.in', 'first_name': 'Faisal', 'last_name': 'Khan',
                'phone': '+91 98473 44556', 'type': Driver.DriverType.DAILY_RENT, 'license': 'KL0720200061234',
                'vehicle': vehicle_map['KL-07-DF-6132'], 'daily_rent': Decimal('850.00')
            },
            {
                'username': 'suresh_p', 'email': 'suresh.p@tourbee.in', 'first_name': 'Suresh', 'last_name': 'Pillai',
                'phone': '+91 98474 55667', 'type': Driver.DriverType.DAILY_RENT, 'license': 'KL0720170010987',
                'vehicle': vehicle_map['KL-07-EC-1098'], 'daily_rent': Decimal('950.00')
            },
            {
                'username': 'akhil_v', 'email': 'akhil.v@tourbee.in', 'first_name': 'Akhil', 'last_name': 'Varghese',
                'phone': '+91 98475 66778', 'type': Driver.DriverType.PROFIT_SHARING, 'license': 'KL0720210098112',
                'vehicle': vehicle_map['KL-07-CJ-9811'], 'daily_rent': Decimal('0.00')
            },
        ]

        driver_map = {}
        for d in drivers_info:
            u, _ = User.objects.get_or_create(
                username=d['username'],
                defaults={
                    'email': d['email'],
                    'first_name': d['first_name'],
                    'last_name': d['last_name'],
                    'role': User.Role.DRIVER,
                    'phone_number': d['phone'],
                    'city': 'Kochi',
                    'state': 'Kerala',
                }
            )
            u.set_password("Driver@2026")
            u.save()

            drv, _ = Driver.objects.get_or_create(
                user=u,
                defaults={
                    'driver_type': d['type'],
                    'license_number': d['license'],
                    'license_expiry': today + timedelta(days=700),
                    'daily_rent_amount': d['daily_rent'],
                    'assigned_vehicle': d['vehicle'],
                    'emergency_contact_name': f"{d['first_name']} Relative",
                    'emergency_contact_phone': '+91 98470 99887',
                    'joining_date': today - timedelta(days=180),
                }
            )
            driver_map[d['username']] = drv
        self.stdout.write(self.style.SUCCESS("✓ Drivers registered (Default password: Driver@2026)."))

        # 6. Generate Realistic Submissions over the past 14 days
        self.stdout.write(self.style.NOTICE("Generating daily Uber submissions and expenses..."))
        gas_stations = [
            "Indian Oil CNG Pump, Palarivattom",
            "BPCL CNG Station, Edappally Toll",
            "HPCL City Gas, Kundannoor Junction",
            "Indian Oil Corporation, Vyttila Hub",
            "Adani Total Gas Station, Aluva Road"
        ]

        for day_offset in range(13, -1, -1):
            sub_date = today - timedelta(days=day_offset)

            for d_info in drivers_info:
                drv = driver_map[d_info['username']]
                veh = d_info['vehicle']
                
                # Check if submission already exists for this driver + date
                if EarningsSubmission.objects.filter(driver=drv, date=sub_date).exists():
                    continue

                # Realistic Uber daily statistics
                trips = random.randint(9, 17)
                online_hrs = Decimal(str(round(random.uniform(7.5, 11.2), 2)))
                gross_earnings = Decimal(str(random.randint(2600, 4800)))
                # Uber commission typically ~20-25%
                commission = (gross_earnings * Decimal(str(round(random.uniform(0.20, 0.23), 3)))).quantize(Decimal('0.01'))
                # Cash collected directly from passengers ~20-35% of gross
                cash_collected = (gross_earnings * Decimal(str(round(random.uniform(0.18, 0.32), 3)))).quantize(Decimal('0.01'))
                toll = Decimal(str(random.choice([0, 80, 160, 240])))

                # Submission status: past days are mostly APPROVED, today/yesterday may have PENDING/CORRECTION
                if day_offset == 0 and drv.user.username == 'rahul_k':
                    status = SubmissionStatus.PENDING
                    reviewed_by = None
                    reviewed_at = None
                    rejection_reason = None
                    correction_notes = None
                elif day_offset == 1 and drv.user.username == 'anoop_m':
                    status = SubmissionStatus.CORRECTION_REQUESTED
                    reviewed_by = admin_user
                    reviewed_at = timezone.now() - timedelta(hours=3)
                    rejection_reason = None
                    correction_notes = "Uber commission entered differs by ₹120 from uploaded statement screenshot. Please verify and re-submit."
                elif day_offset == 2 and drv.user.username == 'akhil_v':
                    status = SubmissionStatus.REJECTED
                    reviewed_by = admin_user
                    reviewed_at = timezone.now() - timedelta(days=1)
                    rejection_reason = "Duplicate date entry submitted without trip breakdown."
                    correction_notes = None
                else:
                    status = SubmissionStatus.APPROVED
                    reviewed_by = admin_user
                    reviewed_at = timezone.now() - timedelta(days=day_offset, hours=2)
                    rejection_reason = None
                    correction_notes = None

                earnings_sub = EarningsSubmission.objects.create(
                    driver=drv,
                    vehicle=veh,
                    date=sub_date,
                    online_hours=online_hrs,
                    trips_count=trips,
                    gross_earnings=gross_earnings,
                    cash_collected=cash_collected,
                    uber_commission=commission,
                    toll_included=toll,
                    other_deductions=Decimal('0.00'),
                    status=status,
                    rejection_reason=rejection_reason,
                    correction_notes=correction_notes,
                    reviewed_by=reviewed_by,
                    reviewed_at=reviewed_at,
                    notes=f"Kochi City Uber Shift - {trips} rides completed"
                )

                AuditEvent.objects.create(
                    target_model='EarningsSubmission',
                    target_id=earnings_sub.id,
                    actor=drv.user if status == SubmissionStatus.PENDING else admin_user,
                    action='SUBMIT' if status == SubmissionStatus.PENDING else status,
                    previous_status=SubmissionStatus.PENDING if status != SubmissionStatus.PENDING else None,
                    new_status=status,
                    notes=correction_notes or rejection_reason or "System initial sync"
                )

                # Add daily CNG expense
                cng_amt = Decimal(str(random.randint(650, 1050)))
                cng_kg = (cng_amt / Decimal('89.50')).quantize(Decimal('0.01')) # ~₹89.5/kg in Kochi
                cng_exp = ExpenseSubmission.objects.create(
                    driver=drv,
                    vehicle=veh,
                    category=cat_objs['CNG'],
                    date=sub_date,
                    amount=cng_amt,
                    odometer_reading=veh.current_odometer - (day_offset * 120),
                    fuel_quantity_kg_or_l=cng_kg,
                    vendor_name=random.choice(gas_stations),
                    description=f"CNG refill {cng_kg} kg @ ₹89.50/kg",
                    paid_by_driver=True,
                    is_operating_expense=True,
                    status=status,
                    reviewed_by=reviewed_by,
                    reviewed_at=reviewed_at
                )

                AuditEvent.objects.create(
                    target_model='ExpenseSubmission',
                    target_id=cng_exp.id,
                    actor=drv.user if status == SubmissionStatus.PENDING else admin_user,
                    action='SUBMIT' if status == SubmissionStatus.PENDING else status,
                    previous_status=SubmissionStatus.PENDING if status != SubmissionStatus.PENDING else None,
                    new_status=status,
                    notes=f"CNG bill ₹{cng_amt}"
                )

                # Occasional toll or car wash expense
                if random.random() < 0.35:
                    toll_amt = Decimal(str(random.choice([85, 110, 160])))
                    toll_exp = ExpenseSubmission.objects.create(
                        driver=drv,
                        vehicle=veh,
                        category=cat_objs['TOLL'],
                        date=sub_date,
                        amount=toll_amt,
                        vendor_name="Kumbalam Toll Plaza / FASTag Kerala",
                        description="FASTag auto-deduction highway trip",
                        paid_by_driver=True,
                        is_operating_expense=True,
                        status=status,
                        reviewed_by=reviewed_by,
                        reviewed_at=reviewed_at
                    )

        self.stdout.write(self.style.SUCCESS("✓ Daily Uber earnings and expense submissions generated with audit trails."))

        # 7. Create Fleet Maintenance Records (Company Expenses - Excluded from driver share)
        maint_data = [
            {
                'veh': vehicle_map['KL-07-CJ-4521'], 'date': today - timedelta(days=18),
                'type': MaintenanceType.SCHEDULED_SERVICE, 'cost': Decimal('4850.00'),
                'garage': 'Popular Maruti Service Center, Edappally', 'odo': 36500,
                'inv': 'PMS-2026-0984', 'notes': '30,000 km general service, engine oil synthetic, oil filter replaced'
            },
            {
                'veh': vehicle_map['KL-07-DE-8924'], 'date': today - timedelta(days=25),
                'type': MaintenanceType.BRAKE_CLUTCH, 'cost': Decimal('3200.00'),
                'garage': 'Sai Service Station, Kalamassery', 'odo': 19800,
                'inv': 'SAI-7721', 'notes': 'Front disc brake pads replacement and brake bleeding'
            },
            {
                'veh': vehicle_map['KL-07-BG-3320'], 'date': today - timedelta(days=3),
                'type': MaintenanceType.AC_SERVICE, 'cost': Decimal('6400.00'),
                'garage': 'Cochin Car Care & Cooling Hub, Vyttila', 'odo': 50800,
                'inv': 'CCC-3312', 'notes': 'AC compressor clutch coil replacement and gas recharge (vehicle grounded in shop)'
            },
            {
                'veh': vehicle_map['KL-07-DF-6132'], 'date': today - timedelta(days=32),
                'type': MaintenanceType.TYRE_REPLACEMENT, 'cost': Decimal('7800.00'),
                'garage': 'Bridgestone Select Tyres, MG Road Kochi', 'odo': 39000,
                'inv': 'BST-1102', 'notes': '2 New front tyres replaced (MRF ZVTV) + 4-wheel laser alignment'
            },
        ]

        for md in maint_data:
            MaintenanceRecord.objects.get_or_create(
                invoice_number=md['inv'],
                defaults={
                    'vehicle': md['veh'],
                    'date': md['date'],
                    'maintenance_type': md['type'],
                    'cost': md['cost'],
                    'vendor_garage': md['garage'],
                    'odometer_reading': md['odo'],
                    'notes': md['notes'],
                    'recorded_by': admin_user
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Company fleet maintenance records logged."))

        # 8. Create Previous Week Salary Calculation and Payment for Profit-Sharing Driver
        last_week_start = today - timedelta(days=14)
        last_week_end = today - timedelta(days=7)
        rahul_drv = driver_map['rahul_k']

        # Approved submissions in that range for Rahul
        r_earnings = EarningsSubmission.objects.filter(
            driver=rahul_drv,
            status=SubmissionStatus.APPROVED,
            date__range=[last_week_start, last_week_end]
        )
        r_gross = sum(e.gross_earnings for e in r_earnings) or Decimal('24500.00')
        r_comm = sum(e.uber_commission for e in r_earnings) or Decimal('5145.00')
        r_cash = sum(e.cash_collected for e in r_earnings) or Decimal('6200.00')

        r_expenses = ExpenseSubmission.objects.filter(
            driver=rahul_drv,
            status=SubmissionStatus.APPROVED,
            date__range=[last_week_start, last_week_end],
            category__is_eligible_for_profit_sharing=True
        )
        r_exp_total = sum(e.amount for e in r_expenses) or Decimal('5800.00')
        r_reimb = sum(e.amount for e in r_expenses.filter(paid_by_driver=True)) or r_exp_total

        # Calculation
        dist_profit = r_gross - r_comm - r_exp_total
        driver_50 = (dist_profit * Decimal('0.50')).quantize(Decimal('0.01'))
        comp_50 = (dist_profit * Decimal('0.50')).quantize(Decimal('0.01'))
        net_driver_pay = driver_50 - r_cash + r_reimb

        calc_record, _ = SalaryCalculation.objects.get_or_create(
            driver=rahul_drv,
            period_start=last_week_start,
            period_end=last_week_end,
            defaults={
                'total_gross_earnings': r_gross,
                'total_commission': r_comm,
                'total_eligible_expenses': r_exp_total,
                'distributable_profit': dist_profit,
                'driver_share_50': driver_50,
                'company_share_50': comp_50,
                'cash_collected_deduction': r_cash,
                'driver_reimbursements': r_reimb,
                'net_payable_to_driver': net_driver_pay,
                'status': CalculationStatus.PAID,
                'notes': "Weekly profit share settlement (Paid via UPI)",
                'calculated_by': admin_user
            }
        )

        SalaryPayment.objects.get_or_create(
            salary_calculation=calc_record,
            driver=rahul_drv,
            defaults={
                'payment_date': last_week_end + timedelta(days=1),
                'amount': net_driver_pay,
                'payment_method': PaymentMethod.UPI,
                'transaction_reference': f"UPI/429188291{random.randint(100, 999)}",
                'notes': f"Direct UPI transfer to {rahul_drv.upi_id}",
                'recorded_by': admin_user
            }
        )
        self.stdout.write(self.style.SUCCESS(f"✓ Rahul Krishnan weekly salary profit-sharing settled: ₹{net_driver_pay}"))

        # 9. Create Rent Records for Daily Rent Drivers
        faisal_drv = driver_map['faisal_k']
        # Rent record for past 7 days
        rent_due_7days = Decimal('850.00') * 7
        RentPayment.objects.get_or_create(
            driver=faisal_drv,
            period_start=today - timedelta(days=7),
            period_end=today - timedelta(days=1),
            defaults={
                'vehicle': faisal_drv.assigned_vehicle,
                'payment_date': today - timedelta(days=1),
                'daily_rate': Decimal('850.00'),
                'days_count': 7,
                'amount_due': rent_due_7days,
                'amount_paid': Decimal('5000.00'), # Outstanding balance of 950!
                'payment_method': PaymentMethod.UPI,
                'transaction_reference': 'UPI/559812984120',
                'notes': 'Partial weekly rent payment by Faisal',
                'recorded_by': admin_user
            }
        )

        suresh_drv = driver_map['suresh_p']
        rent_due_suresh = Decimal('950.00') * 7
        RentPayment.objects.get_or_create(
            driver=suresh_drv,
            period_start=today - timedelta(days=7),
            period_end=today - timedelta(days=1),
            defaults={
                'vehicle': suresh_drv.assigned_vehicle,
                'payment_date': today - timedelta(days=1),
                'daily_rate': Decimal('950.00'),
                'days_count': 7,
                'amount_due': rent_due_suresh,
                'amount_paid': rent_due_suresh, # Fully paid
                'payment_method': PaymentMethod.BANK_TRANSFER,
                'transaction_reference': 'NEFT/HDFC2299104',
                'notes': 'Weekly EV rental paid in full',
                'recorded_by': admin_user
            }
        )
        self.stdout.write(self.style.SUCCESS("✓ Daily rent payment records created for Faisal & Suresh."))

        self.stdout.write(self.style.SUCCESS("""
=============================================================
 TourBee Fleet Manager Seed Completed Successfully!
=============================================================
 Admin Credentials:
   Username: admin
   Password: TourBee@2026

 Driver Credentials:
   - rahul_k (Profit Sharing)  : Driver@2026
   - anoop_m (Profit Sharing)  : Driver@2026
   - faisal_k (Daily Rent)     : Driver@2026
   - suresh_p (Daily Rent)     : Driver@2026
   - akhil_v (Profit Sharing)  : Driver@2026
=============================================================
"""))
