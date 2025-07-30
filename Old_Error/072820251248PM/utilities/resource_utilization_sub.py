from flask import Blueprint, render_template, request
from flask_login import login_required
import pandas as pd
from sqlalchemy import select
from pandas.tseries.holiday import USFederalHolidayCalendar
from models import db, TimesheetEntry

resource_util_bp = Blueprint('resource_util', __name__)

@resource_util_bp.route('/utilities/resource-utilization', methods=['GET', 'POST'])
@login_required
def resource_utilization():
    status_filter = request.args.get('status', 'active')
    service_line_filter = request.args.get('service_line')
    employee_filter = request.args.get('employee')

    # Load timesheet entries and projects table
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
    ts['service_line'] = ts['service_line_proj']
    ts['service_line'] = ts['service_line'].where(~ts['service_line'].isna(), 'Not found in projects source')

    missing_projects = ts.loc[ts['service_line'] == 'Not found in projects source', 'project_name'].unique().tolist()
    unexpected_service_lines = sorted(set(ts['service_line'].unique()) - set(allowed_service_lines) - {'Not found in projects source'})

    ts = ts[ts['service_line'].isin(allowed_service_lines + ['Not found in projects source'])]

    if service_line_filter:
        ts = ts[ts['service_line'] == service_line_filter]
    if employee_filter:
        ts = ts[ts['employee_name'] == employee_filter]

    service_lines = allowed_service_lines
    employees = sorted(ts['employee_name'].dropna().unique())

    ts['month'] = pd.to_datetime(ts['date']).dt.to_period('M')
    ts['billable_flag'] = ts['billable'].apply(lambda x: str(x).strip().lower() in ['yes', 'true', '1'])

    billable_ts = ts[ts['billable_flag'] == True].copy()

    agg = billable_ts.groupby(['employee_name', 'project_name', 'service_line', 'month'])['hours'].sum().reset_index()
    agg = agg.rename(columns={'hours': 'billable_hours'})

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

    months = sorted(agg['month'].unique())
    month_labels = [m.strftime('%b %y') for m in months]

    # Pivot so each row is (employee, project, service line), columns for each month and metric
    pivot = agg.pivot_table(
        index=['employee_name', 'project_name', 'service_line'],
        columns='month',
        values=['billable_capacity', 'billable_hours', 'billable_utilization'],
        fill_value=0,
        aggfunc='first'
    )
    pivot.columns = [f"{col[0]}__{col[1].strftime('%b%y')}" for col in pivot.columns]
    pivot = pivot.reset_index()

    # Build a dict for quick access: {(employee, month): [row indices in pivot]}
    emp_month_projects = {}
    for idx, row in pivot.iterrows():
        emp = row['employee_name']
        for m in months:
            key = m.strftime('%b%y')
            if row.get(f'billable_hours__{key}', 0) > 0 or row.get(f'billable_capacity__{key}', 0) > 0:
                emp_month_projects.setdefault((emp, key), []).append(idx)

    # For non-billable hours: sum all non-billable hours for that employee/month
    nonbill_agg = ts[ts['billable_flag'] == False].groupby(['employee_name', 'month'])['hours'].sum().reset_index()
    nonbill_agg = nonbill_agg.rename(columns={'hours': 'non_billable_hours'})

    def safe_sum(vals):
        return sum(v if isinstance(v, (int, float)) and v != '' else 0 for v in vals)

    # Build the final table: for each employee, output project rows, and after the last project for a month, insert subtotal if needed
    final_table = []
    for emp in sorted(pivot['employee_name'].unique()):
        emp_rows = pivot[pivot['employee_name'] == emp]
        # For each project, add it once
        for _, row in emp_rows.iterrows():
            base = {
                'employee_name': row['employee_name'],
                'project_name': row['project_name'] if row['project_name'] else "Internal Projects",
                'service_line': row['service_line'],
                'is_subtotal': False,
            }
            for m in months:
                key = m.strftime('%b%y')
                base[f'billable_capacity__{key}'] = int(row.get(f'billable_capacity__{key}', 0))
                base[f'billable_hours__{key}'] = float(row.get(f'billable_hours__{key}', 0))
                base[f'billable_utilization__{key}'] = row.get(f'billable_utilization__{key}', "0%")
                base[f'active__{key}'] = row.get(f'billable_hours__{key}', 0) > 0
            final_table.append(base)
        # For each month, if >1 project, insert subtotal after last project for that month
        for m in months:
            key = m.strftime('%b%y')
            indices = emp_month_projects.get((emp, key), [])
            if len(indices) > 1:
                # Find the last project for this month in final_table
                last_proj_idx = max(indices, default=None)
                # Build subtotal row for this month
                subtotal_row = {
                    'employee_name': emp,
                    'project_name': '',
                    'service_line': '+'.join(sorted(set([final_table[i]['service_line'] for i in indices]))),
                    'is_subtotal': True,
                }
                # Use .get to avoid KeyError for missing columns!
                vals_capacity = [final_table[i].get(f'billable_capacity__{key}', 0) for i in indices]
                vals_hours = [final_table[i].get(f'billable_hours__{key}', 0) for i in indices]
                # If you have non-billable per project, use .get as well; otherwise, set to 0
                vals_nonbill = [final_table[i].get(f'non_billable_hours__{key}', 0) for i in indices]
                subtotal_row[f'billable_capacity__{key}'] = safe_sum(vals_capacity)
                subtotal_row[f'billable_hours__{key}'] = safe_sum(vals_hours)
                subtotal_row[f'non_billable_hours__{key}'] = safe_sum(vals_nonbill)
                cap = subtotal_row[f'billable_capacity__{key}']
                bh = subtotal_row[f'billable_hours__{key}']
                nbh = subtotal_row[f'non_billable_hours__{key}']
                subtotal_row[f'billable_utilization__{key}'] = f"{int(round(bh/cap*100))}%" if cap > 0 else "0%"
                subtotal_row[f'non_billable_pct__{key}'] = f"{int(round(nbh/cap*100))}%" if cap > 0 else "0%"
                subtotal_row[f'active__{key}'] = bh > 0
                # All other months: blank
                for mm in months:
                    k2 = mm.strftime('%b%y')
                    if k2 != key:
                        subtotal_row[f'billable_capacity__{k2}'] = ''
                        subtotal_row[f'billable_hours__{k2}'] = ''
                        subtotal_row[f'non_billable_hours__{k2}'] = ''
                        subtotal_row[f'billable_utilization__{k2}'] = ''
                        subtotal_row[f'non_billable_pct__{k2}'] = ''
                        subtotal_row[f'active__{k2}'] = ''
                # Insert subtotal row after the last project for this month
                insert_pos = max([i for i, r in enumerate(final_table) if r['employee_name'] == emp and i in indices], default=None)
                if insert_pos is not None:
                    final_table.insert(insert_pos + 1, subtotal_row)

    return render_template('utilities/resource_utilization.html',
        table=final_table,
        months=months,
        month_labels=month_labels,
        status_filter=status_filter,
        service_lines=service_lines,
        employees=employees,
        service_line_colors=service_line_colors,
        missing_projects=missing_projects,
        unexpected_service_lines=unexpected_service_lines
    )