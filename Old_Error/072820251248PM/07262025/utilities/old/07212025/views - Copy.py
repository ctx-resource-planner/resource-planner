from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

utilities_bp = Blueprint('utilities', __name__, url_prefix='/utilities')

# --- Upload Timesheet ---
@utilities_bp.route('/upload_timesheet', methods=['GET', 'POST'])
@login_required
def upload_timesheet():
    if request.method == 'POST':
        flash('Upload Timesheet not implemented.', 'info')
        return redirect(url_for('utilities.upload_timesheet'))
    return render_template('utilities/upload_timesheet.html')

# --- Timesheet Monthly Summary ---
@utilities_bp.route('/timesheet_summary')
@login_required
def timesheet_summary():
    try:
        from app import db
        from models import TimesheetUpload, Employee
        from collections import defaultdict
        from pandas.tseries.holiday import USFederalHolidayCalendar
        import pandas as pd
        
        # Get all timesheet entries (adapted from Jul-18 logic)
        entries = TimesheetUpload.query.order_by(TimesheetUpload.username, TimesheetUpload.local_date).all()
        
        summary = defaultdict(lambda: defaultdict(lambda: {
            "billable_total": 0,
            "non_billable_total": 0,
            "billable_details": [],
            "non_billable_details": [],
            "capacity": 0
        }))
        
        def us_business_days(year, month):
            start = pd.Timestamp(year=year, month=month, day=1)
            end = (start + pd.offsets.MonthEnd(1))
            cal = USFederalHolidayCalendar()
            holidays = cal.holidays(start=start, end=end)
            bdays = pd.bdate_range(start, end, freq='B')
            bdays = bdays.difference(holidays)
            return len(bdays)
        
        # Get employee names for mapping
        employees = {emp.email: emp.name for emp in Employee.query.all()}
        
        for entry in entries:
            emp = employees.get(entry.username, entry.username)  # Use employee name if available
            month = entry.local_date.strftime('%Y-%m')
            year = entry.local_date.year
            month_num = entry.local_date.month
            
            if summary[emp][month]["capacity"] == 0:
                summary[emp][month]["capacity"] = us_business_days(year, month_num) * 8
            
            # Check if billable (adapt to your is_billable field)
            is_billable = str(entry.is_billable).lower() in ['true', '1', 'yes', 'y']
            
            if is_billable:
                summary[emp][month]["billable_total"] += entry.hours
                summary[emp][month]["billable_details"].append(entry)
            else:
                summary[emp][month]["non_billable_total"] += entry.hours
                summary[emp][month]["non_billable_details"].append(entry)
        
        result = []
        for emp, months in summary.items():
            for month, data in months.items():
                capacity = float(data.get("capacity", 0) or 0)
                billable_total = float(data.get("billable_total", 0) or 0)
                non_billable_total = float(data.get("non_billable_total", 0) or 0)
                billable_pct = f"{int(round((billable_total / capacity) * 100))}%" if capacity > 0 else "0%"
                non_billable_pct = f"{int(round((non_billable_total / capacity) * 100))}%" if capacity > 0 else "0%"
                
                row = {
                    "employee_name": emp,
                    "month": month,
                    "billable_total": billable_total,
                    "non_billable_total": non_billable_total,
                    "billable_details": data.get("billable_details", []),
                    "non_billable_details": data.get("non_billable_details", []),
                    "billable_pct": billable_pct,
                    "non_billable_pct": non_billable_pct,
                }
                result.append(row)
        
        result.sort(key=lambda x: (x['employee_name'], x['month']))
        return render_template('utilities/timesheet_summary.html', summary=result)
        
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return render_template('utilities/timesheet_summary.html', summary=[])


# --- Resource Utilization Dashboard (Embedded) ---
#@utilities_bp.route('/streamlit_dashboard')
#@login_required
#def streamlit_dashboard():
     #return render_template('utilities/streamlit_iframe.html')

# --- CloneTsheet Upload ---
@utilities_bp.route('/clone_tsheet_upload', methods=['GET', 'POST'])
@login_required
def clone_tsheet_upload():
    if request.method == 'POST':
        flash('CloneTsheet Upload not implemented.', 'info')
        return redirect(url_for('utilities.clone_tsheet_upload'))
    return render_template('utilities/clone_tsheet_upload.html')

# --- Demo Report ---
@utilities_bp.route('/demo/report')
@login_required
def demo_report():
    data = [
        {
            "sno": 1,
            "name": "Sayan Mitra",
            "march": [
                {"service_line": "SCC", "hours": 10, "color": "#4e79a7"},
                {"service_line": "DTE", "hours": 8, "color": "#f28e2b"},
            ]
        }
    ]
    for row in data:
        row['total'] = sum(split['hours'] for split in row['march'])
    return render_template("demo_report.html", rows=data)

# --- END OF UTILITIES BLUEPRINT ---
