import csv
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime, timedelta
from decimal import Decimal

from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from apps.accounts.permissions import IsAdminUserRole
from apps.vehicles.models import Vehicle
from apps.drivers.models import Driver
from apps.submissions.models import EarningsSubmission, ExpenseSubmission, SubmissionStatus
from apps.finance.models import SalaryCalculation, SalaryPayment, RentPayment, BusinessSettings
from apps.maintenance.models import MaintenanceRecord

class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.localdate()
        first_of_month = today.replace(day=1)

        if user.is_admin:
            # Fleet Admin Dashboard Metrics
            total_vehicles = Vehicle.objects.count()
            active_vehicles = Vehicle.objects.filter(status=Vehicle.Status.ACTIVE).count()
            maintenance_vehicles = Vehicle.objects.filter(status=Vehicle.Status.MAINTENANCE).count()

            total_drivers = Driver.objects.count()
            active_drivers = Driver.objects.filter(is_active=True).count()
            profit_sharing_drivers = Driver.objects.filter(driver_type=Driver.DriverType.PROFIT_SHARING, is_active=True).count()
            daily_rent_drivers = Driver.objects.filter(driver_type=Driver.DriverType.DAILY_RENT, is_active=True).count()

            pending_earnings = EarningsSubmission.objects.filter(status=SubmissionStatus.PENDING).count()
            pending_expenses = ExpenseSubmission.objects.filter(status=SubmissionStatus.PENDING).count()
            total_pending = pending_earnings + pending_expenses

            # Financial metrics for current month
            month_earnings = EarningsSubmission.objects.filter(
                status=SubmissionStatus.APPROVED,
                date__gte=first_of_month,
                date__lte=today
            )
            gross_revenue_month = month_earnings.aggregate(v=Sum('gross_earnings'))['v'] or Decimal('0.00')
            commission_month = month_earnings.aggregate(v=Sum('uber_commission'))['v'] or Decimal('0.00')
            cash_collected_month = month_earnings.aggregate(v=Sum('cash_collected'))['v'] or Decimal('0.00')
            trips_count_month = month_earnings.aggregate(v=Sum('trips_count'))['v'] or 0

            month_expenses = ExpenseSubmission.objects.filter(
                status=SubmissionStatus.APPROVED,
                date__gte=first_of_month,
                date__lte=today
            )
            operating_expenses_month = month_expenses.aggregate(v=Sum('amount'))['v'] or Decimal('0.00')

            month_maintenance = MaintenanceRecord.objects.filter(
                date__gte=first_of_month,
                date__lte=today
            )
            maintenance_cost_month = month_maintenance.aggregate(v=Sum('cost'))['v'] or Decimal('0.00')

            month_rent = RentPayment.objects.filter(
                payment_date__gte=first_of_month,
                payment_date__lte=today
            )
            rent_collected_month = month_rent.aggregate(v=Sum('amount_paid'))['v'] or Decimal('0.00')

            # Salary Calculations for the month
            salary_calculations_month = SalaryCalculation.objects.filter(
                period_end__gte=first_of_month
            )
            driver_payouts_due = salary_calculations_month.aggregate(v=Sum('net_payable_to_driver'))['v'] or Decimal('0.00')
            company_profit_share_month = salary_calculations_month.aggregate(v=Sum('company_share_50'))['v'] or Decimal('0.00')

            # Net Company Profit = Company 50% Profit Share + Rent Collected - Maintenance Expenses
            net_company_profit = company_profit_share_month + rent_collected_month - maintenance_cost_month

            # Document Expiry Warnings (Insurance or Fitness <= 15 days or expired)
            expiring_vehicles = []
            for v in Vehicle.objects.all():
                ins_status = v.insurance_status
                fit_status = v.fitness_status
                if ins_status in ['EXPIRED', 'EXPIRING_SOON'] or fit_status in ['EXPIRED', 'EXPIRING_SOON']:
                    expiring_vehicles.append({
                        'id': v.id,
                        'registration_number': v.registration_number,
                        'model': f"{v.make} {v.model}",
                        'insurance_expiry': v.insurance_expiry.strftime('%d-%m-%Y') if v.insurance_expiry else None,
                        'insurance_status': ins_status,
                        'fitness_expiry': v.fitness_expiry.strftime('%d-%m-%Y') if v.fitness_expiry else None,
                        'fitness_status': fit_status,
                    })

            # Daily trend for past 14 days
            fourteen_days_ago = today - timedelta(days=13)
            daily_stats = []
            for i in range(14):
                day = fourteen_days_ago + timedelta(days=i)
                day_earnings = EarningsSubmission.objects.filter(status=SubmissionStatus.APPROVED, date=day)
                day_gross = day_earnings.aggregate(v=Sum('gross_earnings'))['v'] or Decimal('0.00')
                day_comm = day_earnings.aggregate(v=Sum('uber_commission'))['v'] or Decimal('0.00')
                day_exp = ExpenseSubmission.objects.filter(status=SubmissionStatus.APPROVED, date=day).aggregate(v=Sum('amount'))['v'] or Decimal('0.00')
                daily_stats.append({
                    'date': day.strftime('%d-%m'),
                    'full_date': day.strftime('%d-%m-%Y'),
                    'gross': float(day_gross),
                    'commission': float(day_comm),
                    'operating_expenses': float(day_exp),
                    'net': float(day_gross - day_comm - day_exp)
                })

            return Response({
                'role': 'ADMIN',
                'overview': {
                    'total_vehicles': total_vehicles,
                    'active_vehicles': active_vehicles,
                    'maintenance_vehicles': maintenance_vehicles,
                    'total_drivers': total_drivers,
                    'active_drivers': active_drivers,
                    'profit_sharing_drivers': profit_sharing_drivers,
                    'daily_rent_drivers': daily_rent_drivers,
                    'pending_approvals': total_pending,
                    'pending_earnings_count': pending_earnings,
                    'pending_expenses_count': pending_expenses,
                },
                'financials_month': {
                    'gross_revenue': float(gross_revenue_month),
                    'uber_commission': float(commission_month),
                    'operating_expenses': float(operating_expenses_month),
                    'maintenance_cost': float(maintenance_cost_month),
                    'rent_collected': float(rent_collected_month),
                    'trips_count': trips_count_month,
                    'company_profit_share': float(company_profit_share_month),
                    'net_company_profit': float(net_company_profit),
                    'cash_collected_by_drivers': float(cash_collected_month),
                },
                'daily_stats': daily_stats,
                'expiring_vehicles': expiring_vehicles,
            })

        else:
            # Driver personal dashboard metrics
            if not hasattr(user, 'driver_profile'):
                return Response({'error': 'Driver profile not linked to this account.'}, status=status.HTTP_404_NOT_FOUND)

            driver = user.driver_profile
            # Submissions stats for driver
            my_earnings_month = EarningsSubmission.objects.filter(driver=driver, date__gte=first_of_month, date__lte=today)
            approved_earnings = my_earnings_month.filter(status=SubmissionStatus.APPROVED)
            my_gross = approved_earnings.aggregate(v=Sum('gross_earnings'))['v'] or Decimal('0.00')
            my_comm = approved_earnings.aggregate(v=Sum('uber_commission'))['v'] or Decimal('0.00')
            my_cash = approved_earnings.aggregate(v=Sum('cash_collected'))['v'] or Decimal('0.00')
            my_trips = approved_earnings.aggregate(v=Sum('trips_count'))['v'] or 0

            my_expenses_month = ExpenseSubmission.objects.filter(driver=driver, date__gte=first_of_month, date__lte=today)
            approved_expenses = my_expenses_month.filter(status=SubmissionStatus.APPROVED)
            my_exp_total = approved_expenses.aggregate(v=Sum('amount'))['v'] or Decimal('0.00')

            pending_count = EarningsSubmission.objects.filter(driver=driver, status=SubmissionStatus.PENDING).count() + \
                            ExpenseSubmission.objects.filter(driver=driver, status=SubmissionStatus.PENDING).count()

            correction_count = EarningsSubmission.objects.filter(driver=driver, status=SubmissionStatus.CORRECTION_REQUESTED).count() + \
                               ExpenseSubmission.objects.filter(driver=driver, status=SubmissionStatus.CORRECTION_REQUESTED).count()

            # Latest salary calculation (if profit sharing)
            latest_calc = None
            if driver.driver_type == Driver.DriverType.PROFIT_SHARING:
                calc_obj = SalaryCalculation.objects.filter(driver=driver).order_by('-period_end').first()
                if calc_obj:
                    latest_calc = {
                        'id': calc_obj.id,
                        'period': f"{calc_obj.period_start.strftime('%d-%m-%Y')} to {calc_obj.period_end.strftime('%d-%m-%Y')}",
                        'distributable_profit': float(calc_obj.distributable_profit),
                        'driver_share_50': float(calc_obj.driver_share_50),
                        'cash_collected_deduction': float(calc_obj.cash_collected_deduction),
                        'reimbursements': float(calc_obj.driver_reimbursements),
                        'net_payable': float(calc_obj.net_payable_to_driver),
                        'status': calc_obj.status,
                    }

            # Rent status (if daily rent)
            rent_info = None
            if driver.driver_type == Driver.DriverType.DAILY_RENT:
                rent_payments = RentPayment.objects.filter(driver=driver)
                due = rent_payments.aggregate(v=Sum('amount_due'))['v'] or Decimal('0.00')
                paid = rent_payments.aggregate(v=Sum('amount_paid'))['v'] or Decimal('0.00')
                rent_info = {
                    'daily_rate': float(driver.daily_rent_amount),
                    'total_due': float(due),
                    'total_paid': float(paid),
                    'outstanding_balance': float(max(Decimal('0.00'), due - paid)),
                }

            # Recent 7 days earnings
            seven_days_ago = today - timedelta(days=6)
            recent_daily = []
            for i in range(7):
                d = seven_days_ago + timedelta(days=i)
                sub = EarningsSubmission.objects.filter(driver=driver, date=d).first()
                recent_daily.append({
                    'date': d.strftime('%d-%m'),
                    'gross': float(sub.gross_earnings) if sub and sub.status == SubmissionStatus.APPROVED else 0.0,
                    'status': sub.status if sub else 'NO_SUBMISSION'
                })

            return Response({
                'role': 'DRIVER',
                'driver': {
                    'id': driver.id,
                    'name': driver.full_name,
                    'driver_type': driver.driver_type,
                    'assigned_vehicle': driver.assigned_vehicle.registration_number if driver.assigned_vehicle else 'None',
                    'assigned_vehicle_name': f"{driver.assigned_vehicle.make} {driver.assigned_vehicle.model}" if driver.assigned_vehicle else None,
                },
                'month_summary': {
                    'gross_earnings': float(my_gross),
                    'uber_commission': float(my_comm),
                    'cash_collected': float(my_cash),
                    'trips_count': my_trips,
                    'operating_expenses': float(my_exp_total),
                },
                'pending_submissions_count': pending_count,
                'correction_requested_count': correction_count,
                'latest_salary_calculation': latest_calc,
                'rent_info': rent_info,
                'recent_daily': recent_daily
            })

class FinancialReportsView(APIView):
    permission_classes = [IsAdminUserRole]

    def get(self, request):
        today = timezone.localdate()
        start_date_str = request.query_params.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
        end_date_str = request.query_params.get('end_date', today.strftime('%Y-%m-%d'))

        # Approved Earnings in range
        earnings_qs = EarningsSubmission.objects.filter(
            status=SubmissionStatus.APPROVED,
            date__range=[start_date_str, end_date_str]
        )
        gross_uber = earnings_qs.aggregate(v=Sum('gross_earnings'))['v'] or Decimal('0.00')
        uber_comm = earnings_qs.aggregate(v=Sum('uber_commission'))['v'] or Decimal('0.00')
        cash_collected = earnings_qs.aggregate(v=Sum('cash_collected'))['v'] or Decimal('0.00')
        total_trips = earnings_qs.aggregate(v=Sum('trips_count'))['v'] or 0

        # Approved Operating Expenses in range
        expenses_qs = ExpenseSubmission.objects.filter(
            status=SubmissionStatus.APPROVED,
            date__range=[start_date_str, end_date_str]
        )
        operating_expenses = expenses_qs.aggregate(v=Sum('amount'))['v'] or Decimal('0.00')
        cng_expenses = expenses_qs.filter(category__code='CNG').aggregate(v=Sum('amount'))['v'] or Decimal('0.00')
        toll_expenses = expenses_qs.filter(category__code='TOLL').aggregate(v=Sum('amount'))['v'] or Decimal('0.00')
        other_expenses = operating_expenses - cng_expenses - toll_expenses

        # Rent payments in range
        rent_qs = RentPayment.objects.filter(
            payment_date__range=[start_date_str, end_date_str]
        )
        rent_revenue = rent_qs.aggregate(v=Sum('amount_paid'))['v'] or Decimal('0.00')

        # Maintenance records in range
        maint_qs = MaintenanceRecord.objects.filter(
            date__range=[start_date_str, end_date_str]
        )
        maintenance_costs = maint_qs.aggregate(v=Sum('cost'))['v'] or Decimal('0.00')

        # Profit Sharing calculations in range
        salary_calcs = SalaryCalculation.objects.filter(
            period_end__range=[start_date_str, end_date_str]
        )
        driver_profit_share = salary_calcs.aggregate(v=Sum('driver_share_50'))['v'] or Decimal('0.00')
        company_profit_share = salary_calcs.aggregate(v=Sum('company_share_50'))['v'] or Decimal('0.00')

        # Company Net Operating Profit = Company Profit Share + Rent Revenue - Maintenance
        company_net_profit = company_profit_share + rent_revenue - maintenance_costs

        # Breakdown by vehicle
        vehicle_breakdown = []
        for v in Vehicle.objects.all():
            v_earnings = earnings_qs.filter(vehicle=v).aggregate(v=Sum('gross_earnings'))['v'] or Decimal('0.00')
            v_expenses = expenses_qs.filter(vehicle=v).aggregate(v=Sum('amount'))['v'] or Decimal('0.00')
            v_maint = maint_qs.filter(vehicle=v).aggregate(v=Sum('cost'))['v'] or Decimal('0.00')
            v_trips = earnings_qs.filter(vehicle=v).aggregate(v=Sum('trips_count'))['v'] or 0
            if v_earnings > 0 or v_expenses > 0 or v_maint > 0:
                vehicle_breakdown.append({
                    'id': v.id,
                    'registration': v.registration_number,
                    'model': f"{v.make} {v.model}",
                    'gross_earnings': float(v_earnings),
                    'operating_expenses': float(v_expenses),
                    'maintenance_cost': float(v_maint),
                    'trips': v_trips,
                    'net_fleet_contribution': float(v_earnings - v_expenses - v_maint)
                })

        # Breakdown by driver
        driver_breakdown = []
        for d in Driver.objects.select_related('user', 'assigned_vehicle'):
            d_earnings = earnings_qs.filter(driver=d).aggregate(v=Sum('gross_earnings'))['v'] or Decimal('0.00')
            d_comm = earnings_qs.filter(driver=d).aggregate(v=Sum('uber_commission'))['v'] or Decimal('0.00')
            d_expenses = expenses_qs.filter(driver=d).aggregate(v=Sum('amount'))['v'] or Decimal('0.00')
            d_trips = earnings_qs.filter(driver=d).aggregate(v=Sum('trips_count'))['v'] or 0
            driver_breakdown.append({
                'id': d.id,
                'name': d.full_name,
                'driver_type': d.driver_type,
                'vehicle': d.assigned_vehicle.registration_number if d.assigned_vehicle else 'None',
                'gross_earnings': float(d_earnings),
                'commission': float(d_comm),
                'expenses': float(d_expenses),
                'trips': d_trips,
            })

        return Response({
            'period': {'start_date': start_date_str, 'end_date': end_date_str},
            'summary': {
                'gross_uber_earnings': float(gross_uber),
                'uber_commission': float(uber_comm),
                'cash_collected': float(cash_collected),
                'total_trips': total_trips,
                'operating_expenses': float(operating_expenses),
                'cng_expenses': float(cng_expenses),
                'toll_expenses': float(toll_expenses),
                'other_expenses': float(other_expenses),
                'rent_revenue': float(rent_revenue),
                'maintenance_costs': float(maintenance_costs),
                'driver_profit_share': float(driver_profit_share),
                'company_profit_share': float(company_profit_share),
                'company_net_profit': float(company_net_profit),
            },
            'vehicle_breakdown': vehicle_breakdown,
            'driver_breakdown': driver_breakdown,
        })

class ExportDataView(APIView):
    permission_classes = [IsAdminUserRole]

    def perform_content_negotiation(self, request, force=False):
        # Allow returning raw CSV or Excel binary file without DRF format suffix 404
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        report_type = request.query_params.get('type', 'earnings')
        export_format = request.query_params.get('format', 'csv').lower()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if report_type == 'earnings':
            qs = EarningsSubmission.objects.all().select_related('driver__user', 'vehicle').order_by('-date')
            if start_date:
                qs = qs.filter(date__gte=start_date)
            if end_date:
                qs = qs.filter(date__lte=end_date)
            
            headers = [
                'ID', 'Date', 'Driver Name', 'Vehicle Reg', 'Trips', 'Online Hours',
                'Gross Earnings (INR)', 'Uber Commission (INR)', 'Cash Collected (INR)',
                'Net Earnings (INR)', 'Status'
            ]
            rows = []
            for r in qs:
                rows.append([
                    r.id,
                    r.date.strftime('%d-%m-%Y'),
                    r.driver.full_name,
                    r.vehicle.registration_number,
                    r.trips_count,
                    float(r.online_hours),
                    float(r.gross_earnings),
                    float(r.uber_commission),
                    float(r.cash_collected),
                    float(r.net_earnings),
                    r.status
                ])
            filename = f"tourbee_earnings_{timezone.localdate().strftime('%d_%m_%Y')}"

        elif report_type == 'expenses':
            qs = ExpenseSubmission.objects.all().select_related('driver__user', 'vehicle', 'category').order_by('-date')
            if start_date:
                qs = qs.filter(date__gte=start_date)
            if end_date:
                qs = qs.filter(date__lte=end_date)

            headers = [
                'ID', 'Date', 'Driver Name', 'Vehicle Reg', 'Category',
                'Amount (INR)', 'Vendor', 'Odometer', 'Fuel Qty', 'Paid By Driver', 'Status'
            ]
            rows = []
            for r in qs:
                rows.append([
                    r.id,
                    r.date.strftime('%d-%m-%Y'),
                    r.driver.full_name,
                    r.vehicle.registration_number,
                    r.category.name,
                    float(r.amount),
                    r.vendor_name or '',
                    r.odometer_reading or '',
                    float(r.fuel_quantity_kg_or_l or 0),
                    'Yes' if r.paid_by_driver else 'No',
                    r.status
                ])
            filename = f"tourbee_expenses_{timezone.localdate().strftime('%d_%m_%Y')}"

        elif report_type == 'maintenance':
            qs = MaintenanceRecord.objects.all().select_related('vehicle').order_by('-date')
            if start_date:
                qs = qs.filter(date__gte=start_date)
            if end_date:
                qs = qs.filter(date__lte=end_date)

            headers = [
                'ID', 'Date', 'Vehicle Reg', 'Service Type', 'Cost (INR)',
                'Garage / Workshop', 'Invoice No', 'Odometer', 'Notes'
            ]
            rows = []
            for r in qs:
                rows.append([
                    r.id,
                    r.date.strftime('%d-%m-%Y'),
                    r.vehicle.registration_number,
                    r.get_maintenance_type_display(),
                    float(r.cost),
                    r.vendor_garage,
                    r.invoice_number or '',
                    r.odometer_reading or '',
                    r.notes or ''
                ])
            filename = f"tourbee_maintenance_{timezone.localdate().strftime('%d_%m_%Y')}"

        else:
            return Response({'error': f'Unsupported report type: {report_type}'}, status=status.HTTP_400_BAD_REQUEST)

        # Output format
        if export_format == 'excel':
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = report_type.capitalize()

            # Styling
            header_fill = PatternFill(start_color='064E3B', end_color='064E3B', fill_type='solid')
            header_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')

            ws.append(headers)
            for col_num in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')

            for row in rows:
                ws.append(row)

            # Adjust column widths
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

            buffer = io.BytesIO()
            wb.save(buffer)
            buffer.seek(0)
            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
            return response

        else: # CSV
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
            return response
