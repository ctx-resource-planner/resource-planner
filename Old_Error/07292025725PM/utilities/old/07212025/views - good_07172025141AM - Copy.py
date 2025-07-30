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
                                'service_item': row['service_item']
                            })

                        try:
                            entry = TimesheetEntry(
                                employee_name=row['employee_name'],
                                employee_email=row['employee_email'],
                                service_line=row['service_line'],
                                date=row['date'],
                                hours=hours,
                                client_name=row['client_name'],
                                project_name=row['project_name'],
                                billable=billable,
                                service_item=row['service_item']
                            )
                            db.session.add(entry)
                            count += 1
                        except Exception as e:
                            errors.append(f"Error adding row for {row['employee_name']}: {str(e)}")
                            skipped += 1

                    db.session.commit()
                    success_message = f"Successfully imported {count} rows. Skipped {skipped} rows due to errors."
            except Exception as e:
                errors.append(f"Error processing file: {str(e)}")

    return render_template('utilities/upload_timesheet.html', errors=errors, success_message=success_message)

@utilities_bp.route('/utilities/timesheet-summary')
@login_required
def timesheet_summary():
    # Example summary logic: group by employee and month
    ts = pd.read_sql(select(TimesheetEntry), db.engine)
    ts['month'] = pd.to_datetime(ts['date']).dt.to_period('M')
    summary = ts.groupby(['employee_name', 'month']).agg(
        billable_hours=('hours', lambda x: x[ts.loc[x.index, 'billable'] == True].sum()),
        non_billable_hours=('hours', lambda x: x[ts.loc[x.index, 'billable'] == False].sum()),
        total_hours=('hours', 'sum')
    ).reset_index()
    summary['billable_pct'] = (summary['billable_hours'] / summary['total_hours']).fillna(0).apply(lambda x: f"{int(round(x*100))}%")
    summary['non_billable_pct'] = (summary['non_billable_hours'] / summary['total_hours']).fillna(0).apply(lambda x: f"{int(round(x*100))}%")
    summary = summary.sort_values(['employee_name', 'month'])
    return render_template('utilities/timesheet_summary.html', summary=summary)

@utilities_bp.route('/utilities/resource-utilization', methods=['GET', 'POST'])
@login_required
def resource_utilization():
    status_filter = request.args.get('status', 'active')
    service_line_filter = request.args.get('service_line')
    employee_filter = request.args.get('employee')

    # Load data
    ts = pd.read_sql(select(TimesheetEntry), db.engine)
    projects = pd.read_sql('SELECT project_name, service_line FROM projects', db.engine)

    # Define allowed service lines and color palette
    allowed_service_lines = ['DB', 'DevOps', 'SCC', 'DTE', 'AI', 'CloudOps']
    service_line_colors = {
        'DB': '#A0ECF6',
        'DevOps': '#C6EBB7',
        'SCC': '#FBE2D5',
        'DTE': '#D0D0D0',
        'AI': '#FFFFCC',
        'CloudOps': '#E9ADE3'
    }

    # Merge timesheet with projects to get service line
    ts = ts.merge(projects, on='project_name', how='left', suffixes=('', '_proj'))
    ts['service_line'] = ts['service_line'].where(~ts['service_line'].isna(), 'Not found in projects source')

    # Track missing projects (not found in projects table)
    missing_projects = ts.loc[ts['service_line'] == 'Not found in projects source', 'project_name'].unique().tolist()
    # Track any unexpected service lines
    unexpected_service_lines = sorted(set(ts['service_line'].unique()) - set(allowed_service_lines) - {'Not found in projects source'})

    # Filter to only allowed service lines and missing
    ts = ts[ts['service_line'].isin(allowed_service_lines + ['Not found in projects source'])]

    # Apply filters
    if service_line_filter:
        ts = ts[ts['service_line'] == service_line_filter]
    if employee_filter:
        ts = ts[ts['employee_name'] == employee_filter]

    # Prepare dropdowns
    service_lines = allowed_service_lines
    employees = sorted(ts['employee_name'].dropna().unique())

    # Group and aggregate
    ts['month'] = pd.to_datetime(ts['date']).dt.to_period('M')
    ts['billable_flag'] = ts['billable'].apply(lambda x: str(x).strip().lower() in ['yes', 'true', '1'])

    agg = ts.groupby(['employee_name', 'project_name', 'service_line', 'month', 'billable_flag'])['hours'].sum().unstack(fill_value=0).reset_index()
    agg = agg.rename(columns={True: 'billable_hours', False: 'non_billable_hours'})

    # Billable capacity and utilization
    def us_business_days(year, month):
        start = pd.Timestamp(year=year, month=month, day=1)
        end = (start + pd.offsets.MonthEnd(1))
        cal = USFederalHolidayCalendar()
        holidays = cal.holidays(start=start, end=end)
        bdays = pd.bdate_range(start, end, freq='B')
        bdays = bdays.difference(holidays)
        return len(bdays)

    agg['year'] = agg['month'].dt.year
    agg['month_num'] = agg['month'].dt.month
    agg['billable_capacity'] = agg.apply(lambda row: us_business_days(int(row['year']), int(row['month_num'])) * 8, axis=1)
    agg['billable_utilization'] = (agg['billable_hours'] / agg['billable_capacity']).fillna(0).apply(lambda x: f"{int(round(x*100))}%" if x > 0 else "0%")
    agg['non_billable_pct'] = (agg['non_billable_hours'] / agg['billable_capacity']).fillna(0).apply(lambda x: f"{int(round(x*100))}%" if x > 0 else "0%")

    months = sorted(agg['month'].unique())

    # Identify employees with multiple billable projects
    billable_projects = agg[agg['billable_hours'] > 0].groupby('employee_name')['project_name'].nunique()
    multi_proj_emps = set(billable_projects[billable_projects > 1].index)

    # Build output with activity flag for each month and subtotals
    table_with_subtotals = []
    for emp, emp_rows in agg.groupby('employee_name'):
        emp_rows_list = []
        for _, row in emp_rows.iterrows():
            base = {
                'employee_name': row['employee_name'],
                'project_name': row['project_name'],
                'service_line': row['service_line'],
                'is_subtotal': False,
            }
            for m in months:
                if row['month'] == m:
                    is_active = row['billable_hours'] > 0
                    base[f'active__{m.strftime("%b%y")}'] = is_active
                    base[f'billable_capacity__{m.strftime("%b%y")}'] = int(row['billable_capacity'])
                    base[f'billable_hours__{m.strftime("%b%y")}'] = int(row['billable_hours'])
                    base[f'billable_utilization__{m.strftime("%b%y")}'] = row['billable_utilization']
                    base[f'non_billable_hours__{m.strftime("%b%y")}'] = int(row['non_billable_hours'])
                    base[f'non_billable_pct__{m.strftime("%b%y")}'] = row['non_billable_pct']
            emp_rows_list.append(base)
        table_with_subtotals.extend(emp_rows_list)

        # Add subtotal row if employee has >1 billable project
        if emp in multi_proj_emps:
            subtotal = pd.DataFrame(emp_rows_list)
            subtotal_row = {
                'employee_name': emp,
                'project_name': 'TOTAL',
                'service_line': '',
                'is_subtotal': True,
            }
            for m in months:
                subtotal_row[f'billable_capacity__{m.strftime("%b%y")}'] = subtotal[f'billable_capacity__{m.strftime("%b%y")}'].sum()
                subtotal_row[f'billable_hours__{m.strftime("%b%y")}'] = subtotal[f'billable_hours__{m.strftime("%b%y")}'].sum()
                subtotal_row[f'non_billable_hours__{m.strftime("%b%y")}'] = subtotal[f'non_billable_hours__{m.strftime("%b%y")}'].sum()
                cap = subtotal_row[f'billable_capacity__{m.strftime("%b%y")}']
                bh = subtotal_row[f'billable_hours__{m.strftime("%b%y")}']
                nbh = subtotal_row[f'non_billable_hours__{m.strftime("%b%y")}']
                subtotal_row[f'billable_utilization__{m.strftime("%b%y")}'] = f"{int(round(bh/cap*100))}%" if cap > 0 else "0%"
                subtotal_row[f'non_billable_pct__{m.strftime("%b%y")}'] = f"{int(round(nbh/cap*100))}%" if cap > 0 else "0%"
                subtotal_row[f'active__{m.strftime("%b%y")}'] = bh > 0
            table_with_subtotals.append(subtotal_row)

    month_labels = [m.strftime('%b %y') for m in months]

    return render_template('utilities/resource_utilization.html',
        table=table_with_subtotals,
        months=months,
        month_labels=month_labels,
        status_filter=status_filter,
        service_lines=service_lines,
        employees=employees,
        service_line_colors=service_line_colors,
        missing_projects=missing_projects,
        unexpected_service_lines=unexpected_service_lines
    )