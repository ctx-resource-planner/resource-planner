from flask import Blueprint, render_template, request, abort, send_file, redirect, url_for, flash, current_app, render_template_string
from flask_login import login_required, current_user
from flask_mail import Message, Mail
from .registry import REPORTS
from models import db, EmployeeMonthlyUtilization  # <-- Import your new model here
from sqlalchemy import text
from datetime import datetime, date
import calendar
import pandas as pd
from io import BytesIO

print("VIEWS.PY LOADED")

reports_bp = Blueprint('reports', __name__, template_folder='templates')

# --- Reports List Route for Navbar ---
@reports_bp.route('/reports', methods=['GET'])
@login_required
def reports_list():
    return render_template('reports_list.html', reports=REPORTS)

# --- NEW: Executive Utilization Dashboard ---
@reports_bp.route('/executive-utilization-dashboard')
@login_required
def executive_utilization_dashboard():
    """Executive Utilization Dashboard with Working Splits"""
    print("🚀 EXECUTIVE ROUTE CALLED - WORKING VERSION")
    
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd
        from datetime import datetime
        
        # Query data
        query = (
            db.session.query(
                TimesheetUpload.username,
                TimesheetUpload.local_date,
                TimesheetUpload.is_billable,
                TimesheetUpload.hours,
                TimesheetUpload.service_item,
                TimesheetUpload.project_name,
                Employee.name.label('employee_name'),
                Employee.doj,
                Employee.doe,
                Employee.reporting_manager,
                Employee.designation,
                Employee.location
            )
            .outerjoin(Employee, Employee.email == TimesheetUpload.username)
        )

        sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        df = pd.read_sql(sql, db.engine)
        print(f"📊 Query returned {len(df)} rows")

        if df.empty:
            return render_template('monthwise_utilization_report.html', 
                                 rows=[], months=[], legend={}, 
                                 service_lines=[], projects=[], employees=[])

        # Normalize data
        def normalize_is_billable(val):
            if pd.isnull(val):
                return False
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return bool(val)
            val_str = str(val).strip().lower()
            return val_str in ['yes', 'true', '1', 'y']

        df['is_billable'] = df['is_billable'].apply(normalize_is_billable)
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
        # Fill missing data
        df['employee_name'] = df['employee_name'].fillna(df['username'])
        df['service_item'] = df['service_item'].fillna('Unknown')
        df['project_name'] = df['project_name'].fillna('Unknown')

        # Get months and colors
        months = sorted(df['month_name'].unique())
        service_lines = df['service_item'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Group by employee only
        employee_groups = df.groupby(['username', 'employee_name', 'doj', 'doe', 'reporting_manager', 'designation', 'location'])
        print(f"📊 Processing {len(employee_groups)} employees")
        
        rows = []
        for (username, emp_name, doj, doe, mgr, designation, location), emp_df in employee_groups:
            print(f"📊 Processing: {emp_name}")
            
            primary_service_line = emp_df['service_item'].mode().iloc[0] if not emp_df['service_item'].empty else 'Unknown'

            
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                if not month_df.empty:
                    # Create splits by project AND service line
                    billable_df = month_df[month_df['is_billable']]
                    project_service_splits = billable_df.groupby(['project_name', 'service_item'])['hours'].sum().reset_index()

                    
                    print(f"📊 {emp_name} in {month}: {len(project_service_splits)} splits found")
                    
                    splits = []
                    for _, row in project_service_splits.iterrows():
                        if row['hours'] > 0:
                            splits.append({
                                'service_line': row['service_item'],
                                'project_name': row['project_name'],
                                'hours': row['hours'],
                                'color': service_line_colors.get(row['service_item'], '#999999')
                            })
                    
                    total_billable = month_df[month_df['is_billable']]['hours'].sum()
                    total_nonbillable = month_df[~month_df['is_billable']]['hours'].sum()
                    
                    monthly_data[month] = {
                        'billable_hours': total_billable,
                        'nonbillable_hours': total_nonbillable,
                        'total_hours': total_billable + total_nonbillable,
                        'billable_capacity': 22,
                        'splits': splits
                    }
                else:
                    monthly_data[month] = {
                        'billable_hours': 0,
                        'nonbillable_hours': 0,
                        'total_hours': 0,
                        'billable_capacity': 22,
                        'splits': []
                    }
            
            rows.append({
                'username': username,
                'name': emp_name,
                'service_line': primary_service_line,
                'doj': doj.strftime('%Y-%m-%d') if isinstance(doj, datetime) else str(doj),
                'doe': doe.strftime('%Y-%m-%d') if isinstance(doe, datetime) else str(doe),
                'reporting_manager': mgr,
                'designation': designation,
                'location': location,
                'months': monthly_data
            })
        
        # Filter options
        filter_service_lines = sorted(df['service_item'].unique())
        filter_projects = sorted(df['project_name'].dropna().unique())
        filter_employees = sorted(df['employee_name'].unique())
        
        return render_template_string(EXECUTIVE_TEMPLATE,
                     rows=rows,
                     months=months,
                     legend=service_line_colors,
                     service_lines=filter_service_lines,
                     projects=filter_projects,
                     employees=filter_employees)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Error: {str(e)}", "danger")
        return render_template_string(EXECUTIVE_TEMPLATE, 
                     rows=[], months=[], legend={}, 
                     service_lines=[], projects=[], employees=[])
                             
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('index'))
    
    try:
        # Get utilization data with service line splits
        sql_query = """
        SELECT 
            tu.username,
            CONCAT(tu.first_name, ' ', tu.last_name) as employee_name,
            tu.local_date,
            tu.hours,
            tu.is_billable,
            tu.project_name,
            COALESCE(e.service_line, 'AI') as employee_service_line,
            COALESCE(e.reporting_manager, 'Unknown') as reporting_manager,
            COALESCE(e.designation, 'Unknown') as designation,
            COALESCE(e.location, 'Unknown') as location,
            e.doj,
            e.doe
        FROM timesheet_uploads tu
        LEFT JOIN employees e ON tu.username = e.email
        ORDER BY tu.username, tu.local_date
        """
        
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            return render_template_string(EXECUTIVE_UTILIZATION_TEMPLATE, 
                                        employees=[], months=[], 
                                        service_lines=[], stats={})
        
        # Data processing
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_year'] = df['local_date'].dt.to_period('M')
        df['is_billable'] = df['is_billable'].astype(str).str.lower().isin(['true', 'yes', '1'])
        
        # Get unique months and sort
        months = sorted(df['month_year'].unique())
        month_strings = [str(m) for m in months]
        
        # Service line colors
        service_line_colors = {
            'AI': '#FF6B6B', 'Data': '#4ECDC4', 'Cloud': '#45B7D1',
            'Web': '#96CEB4', 'Mobile': '#FFEAA7', 'DevOps': '#DDA0DD',
            'QA': '#98D8C8', 'Unknown': '#BDC3C7'
        }
        
        # Process employee data
        employees_data = []
        for username in df['username'].unique():
            emp_df = df[df['username'] == username]
            emp_info = emp_df.iloc[0]
            
            # Monthly data
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_year'] == month]
                if not month_df.empty:
                    billable_hours = month_df[month_df['is_billable']]['hours'].sum()
                    non_billable_hours = month_df[~month_df['is_billable']]['hours'].sum()
                    total_hours = billable_hours + non_billable_hours
                    
                    monthly_data[str(month)] = {
                        'billable_hours': round(billable_hours, 1),
                        'non_billable_hours': round(non_billable_hours, 1),
                        'total_hours': round(total_hours, 1),
                        'billable_percentage': round((billable_hours / total_hours * 100) if total_hours > 0 else 0, 1),
                        'non_billable_percentage': round((non_billable_hours / total_hours * 100) if total_hours > 0 else 0, 1)
                    }
                else:
                    monthly_data[str(month)] = {
                        'billable_hours': 0, 'non_billable_hours': 0, 'total_hours': 0,
                        'billable_percentage': 0, 'non_billable_percentage': 0
                    }
            
            # Check if employee is departed
            is_departed = emp_info['doe'] is not None and pd.to_datetime(emp_info['doe']) < datetime.now()
            
            employees_data.append({
                'username': username,
                'employee_name': emp_info['employee_name'],
                'service_line': emp_info['employee_service_line'],
                'reporting_manager': emp_info['reporting_manager'],
                'designation': emp_info['designation'],
                'location': emp_info['location'],
                'doj': emp_info['doj'].strftime('%Y-%m-%d') if emp_info['doj'] else 'N/A',
                'doe': emp_info['doe'].strftime('%Y-%m-%d') if emp_info['doe'] else 'Active',
                'is_departed': is_departed,
                'monthly_data': monthly_data
            })
        
        # Calculate stats
        latest_month = str(months[-1]) if months else None
        active_projects = 0
        active_resources = 0
        
        if latest_month:
            for emp in employees_data:
                if emp['monthly_data'][latest_month]['billable_hours'] > 0:
                    active_resources += 1
            
            # Count unique projects with billable hours in latest month
            latest_projects = df[
                (df['month_year'] == months[-1]) & 
                (df['is_billable'] == True) & 
                (df['hours'] > 0)
            ]['project_name'].nunique()
            active_projects = latest_projects
        
        stats = {
            'active_projects': active_projects,
            'active_resources': active_resources,
            'total_employees': len(employees_data)
        }
        
        return render_template_string(EXECUTIVE_UTILIZATION_TEMPLATE, 
                                    employees=employees_data, 
                                    months=month_strings,
                                    service_lines=service_line_colors,
                                    stats=stats)
        
    except Exception as e:
        flash(f"Error loading utilization data: {str(e)}", "danger")
        return render_template_string(EXECUTIVE_UTILIZATION_TEMPLATE, 
                                    employees=[], months=[], 
                                    service_lines={}, stats={})

# --- Individual Report View Route ---
@reports_bp.route('/reports/<report_key>', methods=['GET'])
@login_required
def report_view(report_key):
    report = REPORTS.get(report_key)
    if not report:
        abort(404)
    sort = request.args.get('sort')
    order = request.args.get('order', 'asc')
    sql = report['sql']
    if sort and sort in report['columns']:
        sql += f' ORDER BY \"{sort}\" {"ASC" if order == "asc" else "DESC"}'
    result = db.session.execute(text(sql))
    rows = result.mappings().all()
    columns = report['columns']
    return render_template(
        'report_view.html',
        report=report,
        report_key=report_key,
        columns=columns,
        rows=rows,
        sort=sort,
        order=order
    )

# --- Helper function to build allocation matrix DataFrame ---
def build_allocation_matrix_df(args):
    allocation_type = args.get('allocation_type', 'sow')
    period_filter = args.get('period_filter', 'future')
    start_month = args.get('start_month')
    end_month = args.get('end_month')
    today = date.today()
    min_date = db.session.execute(text("SELECT MIN(start_date) FROM allocations")).scalar()
    max_date = db.session.execute(text("SELECT MAX(end_date) FROM allocations WHERE end_date IS NOT NULL")).scalar()
    if not min_date or not max_date:
        min_date = today
        max_date = today
    if period_filter == 'future':
        start = date(today.year, today.month, 1)
        end = date(max_date.year, max_date.month, 1)
    elif period_filter == 'past':
        start = date(min_date.year, min_date.month, 1)
        end = date(today.year, today.month, 1)
    elif period_filter == 'ytd':
        start = date(today.year, 1, 1)
        end = date(today.year, today.month, 1)
    else:  # 'all'
        start = date(min_date.year, min_date.month, 1)
        end = date(max_date.year, max_date.month, 1)
    if start_month:
        start = datetime.strptime(start_month, '%Y-%m').date().replace(day=1)
    if end_month:
        end = datetime.strptime(end_month, '%Y-%m').date().replace(day=1)
    months = []
    current = start
    while current <= end:
        months.append(current.strftime('%b-%Y'))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    employees = db.session.execute(
        text("SELECT id, name, service_line FROM employees WHERE is_active=TRUE")
    ).fetchall()
    if allocation_type == 'actual':
        allocation_column = 'billable_allocation_percentage'
    else:
        allocation_column = 'sow_allocation_percentage'
    allocations = db.session.execute(
        text(f"SELECT a.employee_id, a.project_id, a.{allocation_column}, a.start_date, a.end_date, p.project_name "
             f"FROM allocations a JOIN projects p ON a.project_id = p.id")
    ).fetchall()
    data = []
    for emp in employees:
        row = {
            'Employee Name': emp.name,
            'Service Line': emp.service_line
        }
        for m in months:
            year, mon = m.split('-')[1], m.split('-')[0]
            month_num = datetime.strptime(mon, '%b').month
            first_day = date(int(year), month_num, 1)
            last_day = date(int(year), month_num, calendar.monthrange(int(year), month_num)[1])
            allocs = [
                a for a in allocations if a.employee_id == emp.id and
                a.start_date <= last_day and (a.end_date is None or a.end_date >= first_day)
            ]
            projects = "\n".join([f"{a.project_name}: {getattr(a, allocation_column) or 0}%" for a in allocs])
            total_utilized = sum([(getattr(a, allocation_column) or 0) for a in allocs])
            row[m] = f"{projects}\nTotal Utilized: {total_utilized}%" if projects else f"Total Utilized: {total_utilized}%"
        data.append(row)
    df = pd.DataFrame(data)
    return df

# --- Allocation Matrix Route ---
@reports_bp.route('/allocation-matrix', methods=['GET'])
@login_required
def allocation_matrix():
    allocation_type = request.args.get('allocation_type', 'sow')
    period_filter = request.args.get('period_filter', 'future')
    start_month = request.args.get('start_month')
    end_month = request.args.get('end_month')
    today = date.today()
    min_date = db.session.execute(
        text("SELECT MIN(start_date) FROM allocations")
    ).scalar()
    max_date = db.session.execute(
        text("SELECT MAX(end_date) FROM allocations WHERE end_date IS NOT NULL")
    ).scalar()
    if not min_date or not max_date:
        min_date = today
        max_date = today
    if period_filter == 'future':
        start = date(today.year, today.month, 1)
        end = date(max_date.year, max_date.month, 1)
    elif period_filter == 'past':
        start = date(min_date.year, min_date.month, 1)
        end = date(today.year, today.month, 1)
    elif period_filter == 'ytd':
        start = date(today.year, 1, 1)
        end = date(today.year, today.month, 1)
    else:  # 'all'
        start = date(min_date.year, min_date.month, 1)
        end = date(max_date.year, max_date.month, 1)
    if start_month:
        start = datetime.strptime(start_month, '%Y-%m').date().replace(day=1)
    if end_month:
        end = datetime.strptime(end_month, '%Y-%m').date().replace(day=1)
    months = []
    current = start
    while current <= end:
        months.append(current.strftime('%b-%Y'))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    employees = db.session.execute(
        text("SELECT id, name, service_line FROM employees WHERE is_active=TRUE")
    ).fetchall()
    if allocation_type == 'actual':
        allocation_column = 'billable_allocation_percentage'
    else:
        allocation_column = 'sow_allocation_percentage'
    allocations = db.session.execute(
        text(f"SELECT a.employee_id, a.project_id, a.{allocation_column}, a.start_date, a.end_date, p.project_name "
             f"FROM allocations a JOIN projects p ON a.project_id = p.id")
    ).fetchall()
    matrix = {}
    for emp in employees:
        matrix[emp.id] = {
            'name': emp.name,
            'service_line': emp.service_line,
            'rows': []
        }
        for m in months:
            year, mon = m.split('-')[1], m.split('-')[0]
            month_num = datetime.strptime(mon, '%b').month
            first_day = date(int(year), month_num, 1)
            last_day = date(int(year), month_num, calendar.monthrange(int(year), month_num)[1])
            allocs = [
                a for a in allocations if a.employee_id == emp.id and
                a.start_date <= last_day and (a.end_date is None or a.end_date >= first_day)
            ]
            projects = [(a.project_name, getattr(a, allocation_column) or 0) for a in allocs]
            total_utilized = sum([(getattr(a, allocation_column) or 0) for a in allocs])
            total_available = 100 - total_utilized
            matrix[emp.id]['rows'].append({
                'month': m,
                'projects': projects,
                'total_utilized': total_utilized,
                'total_available': total_available
            })
    return render_template(
        'allocation_matrix.html',
        months=months,
        employees=employees,
        matrix=matrix,
        period_filter=period_filter,
        allocation_type=allocation_type,
        today=today
    )

# --- Export to Excel Route ---
@reports_bp.route('/allocation-matrix/excel')
@login_required
def allocation_matrix_excel():
    df = build_allocation_matrix_df(request.args)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        wrap_format = workbook.add_format({'text_wrap': True})
        for idx, col in enumerate(df.columns):
            worksheet.set_column(idx, idx, 25, wrap_format)
    output.seek(0)
    return send_file(output, download_name="allocation_matrix.xlsx", as_attachment=True)

# --- Email Report Route ---
@reports_bp.route('/allocation-matrix/email')
@login_required
def allocation_matrix_email():
    df = build_allocation_matrix_df(request.args)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']
        wrap_format = workbook.add_format({'text_wrap': True})
        for idx, col in enumerate(df.columns):
            worksheet.set_column(idx, idx, 25, wrap_format)
    output.seek(0)
    msg = Message(
        subject="Your Allocation Matrix Report",
        recipients=[current_user.email],
        body="Please find attached the latest allocation matrix report."
    )
    msg.attach("allocation_matrix.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", output.read())
    from app import mail  # Use the actual import path to your global mail instance
    mail.send(msg)
    flash("Report emailed to you!", "success")
    return redirect(url_for('reports.allocation_matrix', **request.args))

# --- Upload Utilization Data Route ---
@reports_bp.route('/upload-utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    if request.method == 'POST':
        file = request.files['file']
        if not file:
            flash('No file selected', 'danger')
            return redirect(request.url)
        df = pd.read_excel(file) if file.filename.endswith('.xls') or file.filename.endswith('.xlsx') else pd.read_csv(file)
        duplicates = 0
        inserted = 0
        for _, row in df.iterrows():
            exists = EmployeeMonthlyUtilization.query.filter_by(
                employee_id=int(row['EmployeeID']),
                service_line=row['ServiceLine'],
                month=row['Month']
            ).first()
            if exists:
                duplicates += 1
                continue
            util = EmployeeMonthlyUtilization(
                employee_id = int(row['EmployeeID']),
                service_line = row['ServiceLine'],
                month = row['Month'],
                billable_hours = int(row['Billable']),
                billable_percent = str(row['Billable Ut']),
                non_billable_hours = int(row['Non-Billab']),
                non_billable_percent = str(row['Non-Billable%']),
                location = row.get('Location', None)
            )
            db.session.add(util)
            inserted += 1
        db.session.commit()
        flash(f'Upload complete: {inserted} new records added, {duplicates} duplicates skipped.', 'success')
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

# --- Executive Utilization Dashboard Template ---
EXECUTIVE_UTILIZATION_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Executive Utilization Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; }
        .container-fluid { background: white; border-radius: 15px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .service-line-badge { padding: 4px 8px; border-radius: 12px; color: white; font-size: 0.8rem; font-weight: bold; }
        .departed { background-color: #f8f9fa !important; opacity: 0.7; }
        .stats-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
        .legend { background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .legend-item { display: inline-block; margin-right: 20px; margin-bottom: 5px; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="mb-3">
        <a href="{{ url_for('reports.reports_list') }}" class="btn btn-secondary">
            <i class="fas fa-arrow-left"></i> Back to Reports
        </a>
        </div>
        <div class="row mb-4">
            <div class="col-md-8">
                <h1 class="mb-0">📊 Executive Utilization Dashboard</h1>
                <p class="text-muted">Employee utilization tracking with service line analysis</p>
            </div>
            <div class="col-md-4">
                <div class="stats-card text-center">
                    <div class="row">
                        <div class="col-4">
                            <h3>{{ stats.active_projects }}</h3>
                            <small>Active Projects</small>
                        </div>
                        <div class="col-4">
                            <h3>{{ stats.active_resources }}</h3>
                            <small>Active Resources</small>
                        </div>
                        <div class="col-4">
                            <h3>{{ stats.total_employees }}</h3>
                            <small>Total Employees</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="legend">
            <strong>📋 Legend:</strong>
            <span class="legend-item"><strong>BU:</strong> Business Unit</span>
            <span class="legend-item"><strong>B-H:</strong> Billable Hours</span>
            <span class="legend-item"><strong>BH%:</strong> Billable Percentage</span>
            <span class="legend-item"><strong>NB-H:</strong> Non-Billable Hours</span>
            <span class="legend-item"><strong>NB%:</strong> Non-Billable Percentage</span>
        </div>

        <div class="table-responsive">
            <table id="utilizationTable" class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Employee</th>
                        <th>BU</th>
                        <th>Manager</th>
                        <th>Status</th>
                        {% for month in months %}
                        <th colspan="5" class="text-center">{{ month }}</th>
                        {% endfor %}
                    </tr>
                    <tr class="table-secondary">
                        <th></th>
                        <th></th>
                        <th></th>
                        <th></th>
                        {% for month in months %}
                        <th>B-H</th>
                        <th>BH%</th>
                        <th>NB-H</th>
                        <th>NB%</th>
                        <th>Total</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for employee in employees %}
                    <tr class="{% if employee.is_departed %}departed{% endif %}">
                        <td><strong>{{ employee.employee_name }}</strong></td>
                        <td>
                            <span class="service-line-badge" style="background-color: {{ service_lines.get(employee.service_line, '#BDC3C7') }};">
                                {{ employee.service_line }}
                            </span>
                        </td>
                        <td>{{ employee.reporting_manager }}</td>
                        <td>
                            {% if employee.is_departed %}
                                <span class="badge bg-secondary">● Departed</span>
                            {% else %}
                                <span class="badge bg-success">● Active</span>
                            {% endif %}
                        </td>
                        {% for month in months %}
                        {% set data = employee.monthly_data[month] %}
                        <td>{{ data.billable_hours }}</td>
                        <td>{{ data.billable_percentage }}%</td>
                        <td>{{ data.non_billable_hours }}</td>
                        <td>{{ data.non_billable_percentage }}%</td>
                        <td><strong>{{ data.total_hours }}</strong></td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="mt-4">
            <a href="{{ url_for('reports.reports_list') }}" class="btn btn-secondary">← Back to Reports</a>
        </div>
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
    <script>
        $(document).ready(function() {
            $('#utilizationTable').DataTable({
                "pageLength": 25,
                "scrollX": true,
                "fixedColumns": { "leftColumns": 4 },
                "order": [[ 0, "asc" ]]
            });
        });
    </script>
</body>
</html>
"""

EXECUTIVE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Executive Utilization Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <h1>Executive Utilization Dashboard</h1>
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Employee</th>
                        {% for month in months %}
                        <th>{{ month }}</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for row in rows %}
                    <tr>
                        <td>{{ row.name }}</td>
                        {% for month in months %}
                        {% set month_data = row.months.get(month, {}) %}
                        <td>
                            {% if month_data.splits %}
                                {% for split in month_data.splits %}
                                <div style="background-color: {{ split.color }}; color: white; padding: 2px 4px; margin: 1px; border-radius: 3px; font-size: 11px;">
                                    {{ split.service_item }}: {{ split.hours }}h
                                </div>
                                {% endfor %}
                            {% else %}
                                {{ month_data.billable_hours|default(0) }}
                            {% endif %}
                        </td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""