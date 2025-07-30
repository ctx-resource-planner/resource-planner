from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required
import pandas as pd
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models import db, TimesheetEntry
from sqlalchemy import select
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay
import matplotlib.colors as mcolors
import math
from sqlalchemy import func, and_
import calendar
import holidays

# Assuming you have a blueprint for reports
reports_bp = Blueprint('reports', __name__, url_prefix='/reports')
utilities_bp = Blueprint('utilities', __name__, template_folder='templates/utilities')

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
REQUIRED_COLUMNS = [
    'fname', 'lname', 'username', 'group', 'local_date', 'hours',
    'jobcode_1', 'jobcode_2', 'billable', 'service item'
]

COLUMN_MAPPING = {
    'employee_name': lambda df: df['fname'].astype(str) + ' ' + df['lname'].astype(str),
    'employee_email': 'username',
    'service_line': 'group',
    'date': 'local_date',
    'hours': 'hours',
    'client_name': 'jobcode_1',
    'project_name': 'jobcode_2',
    'billable': 'billable',
    'service_item': 'service item'
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@utilities_bp.route('/utilities/upload-timesheet', methods=['GET', 'POST'])
@login_required
def upload_timesheet():
    errors = []
    success_message = None

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            errors.append('No file selected.')
        elif not allowed_file(file.filename):
            errors.append('Invalid file type. Please upload an Excel (.xlsx or .xls) file.')
        else:
            try:
                df = pd.read_excel(file)
                missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
                if missing_cols:
                    errors.append(f"Missing required columns: {', '.join(missing_cols)}")
                else:
                    data = {}
                    for key, val in COLUMN_MAPPING.items():
                        if callable(val):
                            data[key] = val(df)
                        else:
                            data[key] = df[val]
                    import_df = pd.DataFrame(data)
                    import_df = import_df.fillna({'client_name': '', 'project_name': '', 'service_item': ''})
                    count = 0
                    skipped = 0

                    print(import_df.head(20))
                    print(import_df.dtypes)

                    for _, row in import_df.iterrows():
                        # Debug: check if hours is not numeric
                        if not isinstance(row['hours'], (int, float)):
                            print(f"BAD HOURS: {row['hours']} ({type(row['hours'])}) for {row['employee_name']}")

                        # Convert billable to boolean, treat NaN or blank as False
                        billable_raw = row['billable']
                        if pd.isna(billable_raw):
                            billable = False
                        elif str(billable_raw).strip().lower() in ['yes', 'true', '1']:
                            billable = True
                        else:
                            billable = False

                        # Ensure hours is a float and valid
                        try:
                            hours = float(row['hours'])
                        except Exception:
                            errors.append(f"Invalid hours value: '{row['hours']}' for employee {row['employee_name']} on {row['date']}. Row skipped.")
                            skipped += 1
                            continue

                        print(f"Row debug: employee={row['employee_name']}, hours={row['hours']}, type(hours)={type(row['hours'])}, project_name={row['project_name']}")
                        print({
                                'employee_name': row['employee_name'],
                                'employee_email': row['employee_email'],
                                'service_line': row['service_line'],
                                'date': row['date'],
                                'hours': hours,
                                'client_name': row['client_name'],
                                'project_name': row['project_name'],
                                'billable': billable,
                                'service_item': row['service_item'],
                        })
                        entry = TimesheetEntry(
                            employee_name=row['employee_name'],
                            employee_email=row['employee_email'],
                            service_line=row['service_line'],
                            date=row['date'],
                            hours=hours,
                            client_name=row['client_name'],
                            project_name=row['project_name'],
                            billable=billable,
                            service_item=row['service_item'],
                        )
                        db.session.add(entry)
                        count += 1
                    db.session.commit()
                    success_message = f"Imported {count} timesheet entries!"
                    if skipped > 0:
                        errors.append(f"Skipped {skipped} rows due to invalid hours values.")
            except Exception as e:
                db.session.rollback()
                errors.append(f'Error processing file: {e}')

    return render_template('utilities/upload-timesheet.html', preview_data=None, errors=errors, success_message=success_message)

@utilities_bp.route('/utilities/timesheet-summary')
@login_required
def timesheet_summary():
    entries = TimesheetEntry.query.order_by(TimesheetEntry.employee_name, TimesheetEntry.date).all()
    from collections import defaultdict
    summary = defaultdict(lambda: defaultdict(lambda: {
        "billable_total": 0,
        "non_billable_total": 0,
        "billable_details": [],
        "non_billable_details": [],
        "capacity": 0
    }))
    from pandas.tseries.holiday import USFederalHolidayCalendar
    import pandas as pd

    def us_business_days(year, month):
        start = pd.Timestamp(year=year, month=month, day=1)
        end = (start + pd.offsets.MonthEnd(1))
        cal = USFederalHolidayCalendar()
        holidays = cal.holidays(start=start, end=end)
        bdays = pd.bdate_range(start, end, freq='B')
        bdays = bdays.difference(holidays)
        return len(bdays)

    for entry in entries:
        emp = entry.employee_name
        month = entry.date.strftime('%Y-%m')
        year = entry.date.year
        month_num = entry.date.month
        if summary[emp][month]["capacity"] == 0:
            summary[emp][month]["capacity"] = us_business_days(year, month_num) * 8
        if entry.billable in [True, 'Yes', 'yes', 1]:
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
    
@utilities_bp.route('/utilities/streamlit-dashboard')
@login_required
def streamlit_dashboard():
    return render_template('utilities/streamlit_iframe.html')


       
@utilities_bp.route('/utilities/clone_tsheet_upload', methods=['GET', 'POST'])
@login_required
def clone_tsheet_upload():
    from models import TimesheetUpload, db
    errors = []
    success_message = None
    import pandas as pd
    import datetime
    import math
    from flask_login import current_user

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            errors.append('No file selected.')
        else:
            try:
                if file.filename.lower().endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)

                COLUMN_MAP = {
                    'username': 'username',
                    'payroll_id': 'payroll_id',
                    'fname': 'first_name',
                    'lname': 'last_name',
                    'number': 'employee_number',
                    'group': 'group_name',
                    'local_date': 'local_date',
                    'local_day': 'local_day',
                    'local_start_time': 'local_start_time',
                    'local_end_time': 'local_end_time',
                    'tz': 'timezone',
                    'hours': 'hours',
                    'jobcode_1': 'client_name',
                    'jobcode_2': 'project_name',
                    'billable': 'is_billable',
                    'class': 'job_class',
                    'department': 'department',
                    'description': 'description',
                    'service item': 'service_item',
                    'location': 'location',
                    'notes': 'notes',
                    'approved_status': 'approved_status',
                    'has_flags': 'has_flags',
                    'flag_types': 'flag_types',
                }
                if 'comments' in df.columns:
                    COLUMN_MAP['comments'] = 'comments'

                count = 0
                skipped = 0
                for idx, row in df.iterrows():
                    record = {}
                    for excel_col, db_col in COLUMN_MAP.items():
                        if excel_col in df.columns:
                            record[db_col] = row[excel_col]
                        else:
                            record[db_col] = None

                    # --- CLEAN NUMERIC FIELDS ---
                    for num_col in ['hours', 'employee_number']:
                        val = record.get(num_col)
                        try:
                            if pd.isna(val) or val == '' or (isinstance(val, str) and not val.strip()):
                                record[num_col] = None
                            else:
                                record[num_col] = float(val)
                        except Exception:
                            record[num_col] = None

                    # --- CLEAN NaN for all fields ---
                    for key, val in record.items():
                        if isinstance(val, float) and math.isnan(val):
                            record[key] = None

                    # Parse date
                    if record['local_date']:
                        try:
                            record['local_date'] = pd.to_datetime(record['local_date']).date()
                        except Exception:
                            record['local_date'] = None

                    # Parse booleans
                    billable_val = str(record.get('is_billable', '')).strip().lower()
                    record['is_billable'] = billable_val in ['yes', 'true', '1']
                    has_flags_val = str(record.get('has_flags', '')).strip().lower()
                    record['has_flags'] = has_flags_val in ['yes', 'true', '1']

                    # Add meta
                    record['uploaded_by'] = getattr(current_user, 'username', 'admin')
                    record['upload_timestamp'] = datetime.datetime.utcnow()
                    # Insert
                    try:
                        db.session.add(TimesheetUpload(**record))
                        count += 1
                    except Exception as e:
                        errors.append(f"Row {idx+1} error: {e}")
                        skipped += 1
                db.session.commit()
                success_message = f"Imported {count} rows successfully. Skipped {skipped} rows."
            except Exception as e:
                db.session.rollback()
                errors.append(f'Error processing file: {e}')
    return render_template('utilities/clone_tsheet_upload.html', errors=errors, success_message=success_message)

@utilities_bp.route('/demo/report')
def demo_report():
    data = [
        {
            "sno": 1,
            "name": "Sayan Mitra",
            "march": [
                {"service_line": "SCC", "hours": 10, "color": "#4e79a7"},
                {"service_line": "DTE", "hours": 8, "color": "#f28e2b"},
            ]
        },
        {
            "sno": 2,
            "name": "Priya Rao",
            "march": [
                {"service_line": "DB", "hours": 16, "color": "#e15759"},
            ]
        },
    ]
    # Calculate total for each row
    for row in data:
        row['total'] = sum(split['hours'] for split in row['march'])
    return render_template("demo_report.html", rows=data)