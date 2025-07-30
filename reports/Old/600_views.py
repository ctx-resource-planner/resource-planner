#python
from flask import Blueprint, render_template, request, abort, send_file, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from flask_mail import Message
from models import db, TimesheetUpload, Project, Employee, EmployeeMonthlyUtilization
from sqlalchemy import text, func
from datetime import datetime, date
import calendar
import holidays
import pandas as pd
from io import BytesIO

# --- Blueprint Registration ---
reports_bp = Blueprint(
    'reports',
    __name__,
    template_folder='templates',
    url_prefix='/reports'
)

# --- Reports List Route for Navbar ---
@reports_bp.route('/', methods=['GET'])
@login_required
def reports_list():
    # If you have a registry of reports, pass it here, else just render the template
    return render_template('reports_list.html')

# --- Monthwise Utilization Report ---
@reports_bp.route('/resource_utilization_report', methods=['GET'])
@login_required
def monthwise_utilization_report():
    # --- 1. Fetch Data ---
    stmt = (
        db.session.query(
            TimesheetUpload.username,
            TimesheetUpload.project_name,
            TimesheetUpload.hours,
            TimesheetUpload.is_billable,
            TimesheetUpload.local_date,
            Project.service_line,
            Employee.name.label("emp_name"),
            Employee.email,
            Employee.doj,
            Employee.doe,
            Employee.reporting_manager,
            Employee.designation,
            Employee.location
        )
        .join(Project, TimesheetUpload.project_name == Project.name)
        .join(Employee, TimesheetUpload.username == Employee.email)
    )

    df = pd.read_sql(stmt.statement, db.engine)

    if df.empty:
        return render_template("monthwise_utilization_report.html", rows=[], months=[], service_lines=[], projects=[], employees=[], legend={})

    # --- 2. Data Preparation ---
    df['local_date'] = pd.to_datetime(df['local_date'])
    df['month'] = df['local_date'].dt.strftime('%b')
    df['year'] = df['local_date'].dt.year
    df['month_year'] = df['local_date'].dt.strftime('%b-%Y')
    df = df[df['year'] == 2025]
    months = sorted(df['month_year'].unique(), key=lambda x: datetime.strptime(x, '%b-%Y'))

    legend = {
        "DB": "#4e79a7",
        "DevOps": "#f28e2b",
        "SCC": "#e15759",
        "DTE": "#76b7b2",
        "AI": "#59a14f",
        "CloudOps": "#edc949"
    }
    service_lines = sorted(df['service_line'].dropna().unique())
    projects = sorted(df['project_name'].dropna().unique())
    employees = sorted(df['emp_name'].dropna().unique())

    # --- 3. Filtering (from dropdowns) ---
    selected_service_line = request.args.get('service_line', '')
    selected_project = request.args.get('project', '')
    selected_employee = request.args.get('employee', '')
    selected_month = request.args.get('month', '')

    if selected_service_line:
        df = df[df['service_line'] == selected_service_line]
    if selected_project:
        df = df[df['project_name'] == selected_project]
    if selected_employee:
        df = df[df['emp_name'] == selected_employee]
    if selected_month:
        df = df[df['month_year'] == selected_month]

    # --- 4. Billable Capacity Calculation ---
    us_holidays = holidays.US(years=[2025])
    month_capacities = {}
    for m in months:
        dt = datetime.strptime(m, '%b-%Y')
        _, last_day = calendar.monthrange(dt.year, dt.month)
        all_days = pd.date_range(start=dt.replace(day=1), end=dt.replace(day=last_day))
        business_days = [d for d in all_days if d.weekday() < 5 and d not in us_holidays]
        month_capacities[m] = len(business_days)

    # --- 5. Aggregation ---
    report_rows = []
    for emp, emp_df in df.groupby('emp_name'):
        emp_info = emp_df.iloc[0]
        emp_row = {
            "name": emp,
            "service_line": emp_info['service_line'],
            "doj": emp_info['doj'].strftime('%Y-%m-%d') if pd.notnull(emp_info['doj']) else '',
            "doe": emp_info['doe'].strftime('%Y-%m-%d') if pd.notnull(emp_info['doe']) else '',
            "reporting_manager": emp_info['reporting_manager'],
            "designation": emp_info['designation'],
            "location": emp_info['location'],
            "months": {}
        }
        for m in months:
            mdf = emp_df[emp_df['month_year'] == m]
            splits = []
            total_hours = mdf['hours'].sum()
            billable_hours = mdf[mdf['is_billable'] == True]['hours'].sum()
            nonbillable_hours = mdf[mdf['is_billable'] == False]['hours'].sum()
            for sl, sdf in mdf.groupby('service_line'):
                hrs = sdf['hours'].sum()
                billable = sdf[sdf['is_billable'] == True]['hours'].sum()
                nonbillable = sdf[sdf['is_billable'] == False]['hours'].sum()
                splits.append({
                    "service_line": sl,
                    "hours": hrs,
                    "color": legend.get(sl, "#999"),
                    "billable": billable,
                    "nonbillable": nonbillable
                })
            # Billable Capacity logic
            doj = emp_info['doj']
            doe = emp_info['doe']
            dt = datetime.strptime(m, '%b-%Y')
            _, last_day = calendar.monthrange(dt.year, dt.month)
            month_start = dt.replace(day=1)
            month_end = dt.replace(day=last_day)
            month_start_date = month_start.date() if hasattr(month_start, 'date') else month_start
            month_end_date = month_end.date() if hasattr(month_end, 'date') else month_end
            doj_date = doj.date() if hasattr(doj, 'date') else doj
            doe_date = doe.date() if hasattr(doe, 'date') else doe
            active_start = max(month_start_date, doj_date) if pd.notnull(doj_date) else month_start_date
            active_end = min(month_end_date, doe_date) if pd.notnull(doe_date) else month_end_date
            all_days = pd.date_range(start=active_start, end=active_end)
            business_days = [d for d in all_days if d.weekday() < 5 and d not in us_holidays]
            billable_capacity = len(business_days)
            if pd.notnull(doj) and active_end < doj:
                billable_capacity = 0
            if pd.notnull(doe) and active_start > doe:
                billable_capacity = 0
            emp_row['months'][m] = {
                "splits": splits,
                "total_hours": total_hours,
                "billable_hours": billable_hours,
                "nonbillable_hours": nonbillable_hours,
                "billable_capacity": billable_capacity
            }
        report_rows.append(emp_row)

    return render_template(
        "monthwise_utilization_report.html",
        rows=report_rows,
        months=months,
        service_lines=service_lines,
        projects=projects,
        employees=employees,
        legend=legend,
        selected_service_line=selected_service_line,
        selected_project=selected_project,
        selected_employee=selected_employee,
        selected_month=selected_month
    )

# --- Download as Excel ---
@reports_bp.route('/utilization_excel')
@login_required
def utilization_excel():
    # TODO: Use the same logic as in monthwise_utilization_report to get your DataFrame
    # For demo, just return a dummy Excel
    df = pd.DataFrame([{"Employee": "Test", "Hours": 40}])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Utilization')
    output.seek(0)
    return send_file(output, download_name="utilization_report.xlsx", as_attachment=True)

# --- Email Report ---
@reports_bp.route('/utilization_email')
@login_required
def utilization_email():
    # TODO: Use the same logic as in monthwise_utilization_report to get your DataFrame
    df = pd.DataFrame([{"Employee": "Test", "Hours": 40}])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Utilization')
    output.seek(0)
    msg = Message(
        subject="Your Utilization Report",
        recipients=[current_user.email],
        body="Attached is your utilization report."
    )
    msg.attach("utilization_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", output.read())
    from app import mail  # Adjust import as needed
    mail.send(msg)
    flash("Report emailed to you!", "success")
    return redirect(url_for('reports.monthwise_utilization_report'))

# --- Allocation Matrix ---
@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    # Dummy implementation, replace with your logic
    return render_template('allocation_matrix.html')

# --- Upload Utilization Data ---
@reports_bp.route('/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    if request.method == 'POST':
        # Your upload logic here
        flash('Upload complete!', 'success')
        return redirect(url_for('reports.upload_utilization'))
    return render_template('upload_utilization.html')

# --- Utilization Report Route ---
@reports_bp.route('/utilization-report')
@login_required
def utilization_report():
    from models import Employee  # Ensure Employee model is imported
    service_line = request.args.get('service_line')
    month = request.args.get('month')
    query = EmployeeMonthlyUtilization.query
    if service_line:
        query = query.filter_by(service_line=service_line)
    if month:
        query = query.filter_by(month=month)
    data = query.all()
    employee_ids = [row.employee_id for row in data]
    employees = Employee.query.filter(Employee.id.in_(employee_ids)).all() if employee_ids else []
    emp_map = {e.id: e.name for e in employees}
    return render_template('utilization_report.html', data=data, emp_map=emp_map)
    
    from flask import send_file
import pandas as pd
from io import BytesIO
from sqlalchemy import text

@reports_bp.route('/reports/<report_key>/download')
@login_required
def report_download(report_key):
    report = REPORTS.get(report_key)
    if not report:
        abort(404)
    sql = report['sql']
    result = db.session.execute(text(sql))
    rows = result.mappings().all()
    columns = report.get('columns', [])
    df = pd.DataFrame(rows, columns=columns if columns else None)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
        # Optional: add formatting like in allocation matrix
        workbook = writer.book
        worksheet = writer.sheets['Report']
        wrap_format = workbook.add_format({'text_wrap': True})
        for idx, col in enumerate(df.columns):
            worksheet.set_column(idx, idx, 25, wrap_format)
    output.seek(0)
    filename = f"{report_key}_report.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@reports_bp.route('/reports/<report_key>/email', methods=['POST'])
@login_required
def report_email(report_key):
    report = REPORTS.get(report_key)
    if not report:
        abort(404)
    sql = report['sql']
    result = db.session.execute(text(sql))
    rows = result.mappings().all()
    columns = report.get('columns', [])
    df = pd.DataFrame(rows, columns=columns if columns else None)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')
        workbook = writer.book
        worksheet = writer.sheets['Report']
        wrap_format = workbook.add_format({'text_wrap': True})
        for idx, col in enumerate(df.columns):
            worksheet.set_column(idx, idx, 25, wrap_format)
    output.seek(0)
    filename = f"{report_key}_report.xlsx"

    msg = Message(
        subject=f"{report['title']} - Export",
        recipients=[current_user.email],
        body=f"Attached is the {report['title']} you requested.",
        sender=current_app.config.get("MAIL_DEFAULT_SENDER")
    )
    msg.attach(filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", output.read())
    from app import mail  # Use the actual import path to your global mail instance
    mail.send(msg)
    flash('Report emailed to you!', 'success')
    return redirect(url_for('reports.report_view', report_key=report_key))




@reports_bp.route('/resource_utilization_report', methods=['GET'])
@login_required
def monthwise_utilization_report():
    # --- 1. Fetch Data ---
    from app import db
    from models import TimesheetUpload, Project, Employee
    from sqlalchemy import select

    # Join timesheet_uploads, projects, employees (by username/email and project_name)
    stmt = select(
        TimesheetUpload.username,
        TimesheetUpload.project_name,
        TimesheetUpload.hours,
        TimesheetUpload.is_billable,
        TimesheetUpload.local_date,
        Project.service_line,
        Employee.name.label("emp_name"),
        Employee.email,
        Employee.doj,
        Employee.doe,
        Employee.reporting_manager,
        Employee.designation,
        Employee.location
    ).select_from(
        TimesheetUpload
    ).join(Project, TimesheetUpload.project_name == Project.name
    ).join(Employee, TimesheetUpload.username == Employee.email)

    df = pd.read_sql(stmt, db.engine)
    


    if df.empty:
        return render_template("monthwise_utilization_report.html", rows=[], months=[], service_lines=[], projects=[], employees=[], legend={})

    # --- 2. Data Preparation ---
    # Parse dates, add month/year columns
    df['local_date'] = pd.to_datetime(df['local_date'])
    df['month'] = df['local_date'].dt.strftime('%b')
    df['year'] = df['local_date'].dt.year
    df['month_year'] = df['local_date'].dt.strftime('%b-%Y')

    # Filter for 2025 only (as per your data)
    df = df[df['year'] == 2025]

    # Get all months in data, sorted
    months = sorted(df['month_year'].unique(), key=lambda x: datetime.strptime(x, '%b-%Y'))

    # Service line color legend
    legend = {
        "DB": "#4e79a7",
        "DevOps": "#f28e2b",
        "SCC": "#e15759",
        "DTE": "#76b7b2",
        "AI": "#59a14f",
        "CloudOps": "#edc949"
    }

    # Dropdown options
    service_lines = sorted(df['service_line'].dropna().unique())
    projects = sorted(df['project_name'].dropna().unique())
    employees = sorted(df['emp_name'].dropna().unique())

    # --- 3. Filtering (from dropdowns) ---
    selected_service_line = request.args.get('service_line', '')
    selected_project = request.args.get('project', '')
    selected_employee = request.args.get('employee', '')
    selected_month = request.args.get('month', '')

    if selected_service_line:
        df = df[df['service_line'] == selected_service_line]
    if selected_project:
        df = df[df['project_name'] == selected_project]
    if selected_employee:
        df = df[df['emp_name'] == selected_employee]
    if selected_month:
        df = df[df['month_year'] == selected_month]

    # --- 4. Billable Capacity Calculation ---
    us_holidays = holidays.US(years=[2025])
    month_capacities = {}
    for m in months:
        dt = datetime.strptime(m, '%b-%Y')
        _, last_day = calendar.monthrange(dt.year, dt.month)
        all_days = pd.date_range(start=dt.replace(day=1), end=dt.replace(day=last_day))
        business_days = [d for d in all_days if d.weekday() < 5 and d not in us_holidays]
        month_capacities[m] = len(business_days)

    # --- 5. Aggregation ---
    # Group by employee, month, service line
    report_rows = []
    for emp, emp_df in df.groupby('emp_name'):
        emp_info = emp_df.iloc[0]
        emp_row = {
            "name": emp,
            "service_line": emp_info['service_line'],
            "doj": emp_info['doj'].strftime('%Y-%m-%d') if pd.notnull(emp_info['doj']) else '',
            "doe": emp_info['doe'].strftime('%Y-%m-%d') if pd.notnull(emp_info['doe']) else '',
             "reporting_manager": emp_info['reporting_manager'],
            "designation": emp_info['designation'],
            "location": emp_info['location'],
            "months": {}
    }
        for m in months:
            mdf = emp_df[emp_df['month_year'] == m]
            splits = []
            total_hours = mdf['hours'].sum()
            billable_hours = mdf[mdf['is_billable'] == True]['hours'].sum()
            # NEW: Non-billable hours is the sum of ALL non-billable entries for the month (regardless of project)
            nonbillable_hours = mdf[mdf['is_billable'] == False]['hours'].sum()
            for sl, sdf in mdf.groupby('service_line'):
                hrs = sdf['hours'].sum()
                billable = sdf[sdf['is_billable'] == True]['hours'].sum()
                nonbillable = sdf[sdf['is_billable'] == False]['hours'].sum()
                splits.append({
                    "service_line": sl,
                    "hours": hrs,
                    "color": legend.get(sl, "#999"),
                    "billable": billable,
                    "nonbillable": nonbillable
            })
        # Billable Capacity logic
        doj = emp_info['doj']
        doe = emp_info['doe']
        dt = datetime.strptime(m, '%b-%Y')
        _, last_day = calendar.monthrange(dt.year, dt.month)
        month_start = dt.replace(day=1)
        month_end = dt.replace(day=last_day)
        # Ensure all are date objects for comparison
        month_start_date = month_start.date() if hasattr(month_start, 'date') else month_start
        month_end_date = month_end.date() if hasattr(month_end, 'date') else month_end
        doj_date = doj.date() if hasattr(doj, 'date') else doj
        doe_date = doe.date() if hasattr(doe, 'date') else doe
        active_start = max(month_start_date, doj_date) if pd.notnull(doj_date) else month_start_date
        active_end = min(month_end_date, doe_date) if pd.notnull(doe_date) else month_end_date
        all_days = pd.date_range(start=active_start, end=active_end)
        business_days = [d for d in all_days if d.weekday() < 5 and d not in us_holidays]
        billable_capacity = len(business_days)
        if pd.notnull(doj) and active_end < doj:
            billable_capacity = 0
        if pd.notnull(doe) and active_start > doe:
            billable_capacity = 0
        emp_row['months'][m] = {
            "splits": splits,
            "total_hours": total_hours,
            "billable_hours": billable_hours,
            "nonbillable_hours": nonbillable_hours,  # <-- Now correct!
            "billable_capacity": billable_capacity
        }
        report_rows.append(emp_row)

        return render_template(
        "monthwise_utilization_report.html",
        rows=report_rows,
        months=months,
        service_lines=service_lines,
        projects=projects,
        employees=employees,
        legend=legend,
        selected_service_line=selected_service_line,
        selected_project=selected_project,
        selected_employee=selected_employee,
        selected_month=selected_month
    )
    
from flask import Blueprint, request, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
import pandas as pd
import io

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports/utilization_excel')
@login_required
def utilization_excel():
    # Use your existing report query logic here to get the same filtered DataFrame as the report
    # For demo, let's assume you have a function get_utilization_report_df(request.args)
    df = get_utilization_report_df(request.args)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Utilization')
        # Optionally, add formatting here!
    output.seek(0)
    return send_file(output, download_name="utilization_report.xlsx", as_attachment=True)

@reports_bp.route('/reports/utilization_email')
@login_required
def utilization_email():
    # Use your existing report query logic here to get the same filtered DataFrame as the report
    df = get_utilization_report_df(request.args)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Utilization')
    output.seek(0)
    # Now send as email attachment
    from flask_mail import Message
    from your_flask_app import mail  # adjust import as needed
    msg = Message(
        subject="Your Utilization Report",
        recipients=[current_user.email],
        body="Attached is your utilization report."
    )
    msg.attach("utilization_report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", output.read())
    mail.send(msg)
    flash("Report emailed to you!", "success")
    return redirect(url_for('reports.utilization_report', **request.args))
    
@reports_bp.route('/reports/allocation_matrix')
@login_required
def allocation_matrix():
    # Your logic here
    return render_template('allocation_matrix.html')
    
@reports_bp.route('/reports/list')
@login_required
def reports_list():
    # Render a list of available reports, or redirect as needed
    return render_template('reports_list.html')

@reports_bp.route('/reports/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    # Your upload logic here
    return render_template('upload_utilization.html')
    
@reports_bp.route('/reports/resource_utilization_report')
@login_required
def resource_utilization_report():
    # Your logic here
    return render_template('monthwise_utilization_report.html', ...)