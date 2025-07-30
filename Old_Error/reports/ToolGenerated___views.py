from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from sqlalchemy import extract
from io import BytesIO
import pandas as pd

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# --- Main Reports List Page ---
@reports_bp.route('/working_utilization_report')
@login_required
def working_utilization_report():
    """WORKING Utilization Report - Final Solution."""
    legend = {
        "Act": "Active Days",
        "Cap": "Capacity",
        "BHrs": "Billable Hours",
        "B%": "Billable %",
        "NBHrs": "Non-Billable Hours"
    }
    
    data = []  # Initialize empty data
    
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd

        # Query timesheet data
        query = (
            db.session.query(
                TimesheetUpload.username,
                TimesheetUpload.local_date,
                TimesheetUpload.is_billable,
                TimesheetUpload.hours,
                Employee.name.label('employee_name')
            )
            .outerjoin(Employee, Employee.email == TimesheetUpload.username)
        )

        # Compile query properly for pandas
        sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        df = pd.read_sql(sql, db.engine)

        if not df.empty:
            # Normalize is_billable field
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
            df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%Y-%m')

            # Aggregate by employee and month
            grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
                billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
                non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
                total_hours=pd.NamedAgg(column='hours', aggfunc='sum')
            ).reset_index()

            data = grouped.to_dict(orient='records')

    except Exception as e:
        # If there's an error, we'll still return the template with empty data
        flash(f"Error loading data: {str(e)}", "danger")

    # This return statement will ALWAYS execute
    return render_template('monthwise_utilization_report.html', data=data, legend=legend)
        

# --- Other Report Routes ---
@reports_bp.route('/projects_summary')
@login_required
def projects_summary():
    return render_template('projects_list.html')

@reports_bp.route('/skills_proficiency')
@login_required
def skills_proficiency():
    return render_template('skills_list.html')

@reports_bp.route('/projects_billable_allocation')
@login_required
def projects_billable_allocation():
    return render_template('report_view.html')

@reports_bp.route('/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    if request.method == 'POST':
        flash('Upload Utilization not implemented.', 'info')
        return redirect(url_for('reports.upload_utilization'))
    return render_template('upload_utilization.html')

@reports_bp.route('/resource_utilization_dashboard')
@login_required
def resource_utilization_dashboard():
    return render_template('utilities/streamlit_iframe.html')

# --- Aliases ---
#@reports_bp.route('/resource_utilization_report')
#@login_required
#def resource_utilization_report():
    #return redirect(url_for('reports.monthwise_utilization_report'))

# --- Excel Export ---
@reports_bp.route('/monthwise_utilization_report/excel')
@login_required
def utilization_excel():
    try:
        from app import db
        from models import TimesheetUpload, Employee

        query = (
            db.session.query(
                TimesheetUpload.username,
                TimesheetUpload.local_date,
                TimesheetUpload.is_billable,
                TimesheetUpload.hours,
                Employee.name.label('employee_name')
            )
            .outerjoin(Employee, Employee.email == TimesheetUpload.username)
        )

        sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        df = pd.read_sql(sql, db.engine)

        if not df.empty:
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
            df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%Y-%m')

            grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
                billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
                non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
                total_hours=pd.NamedAgg(column='hours', aggfunc='sum')
            ).reset_index()

            output = BytesIO()
            grouped.to_excel(output, index=False, sheet_name='Utilization Report')
            output.seek(0)

            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='utilization_report.xlsx'
            )
        else:
            flash('No data available for export.', 'warning')
            return redirect(url_for('reports.monthwise_utilization_report'))

    except Exception as e:
        flash(f'Error exporting to Excel: {str(e)}', 'danger')
        return redirect(url_for('reports.monthwise_utilization_report'))

# --- Email Export ---
@reports_bp.route('/monthwise_utilization_report/email')
@login_required
def utilization_email():
    flash('Email export feature not implemented yet.', 'info')
    return redirect(url_for('reports.monthwise_utilization_report'))
    
# --- NEW WORKING ROUTE (bypasses cache issues) ---
@reports_bp.route('/utilization_report_new')
@login_required
def utilization_report_new():
    """NEW Working Utilization Report - Bypasses cache issues."""
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd
        from sqlalchemy import extract

        # Simple query first
        query = (
            db.session.query(
                TimesheetUpload.username,
                TimesheetUpload.local_date,
                TimesheetUpload.is_billable,
                TimesheetUpload.hours,
                Employee.name.label('employee_name')
            )
            .outerjoin(Employee, Employee.email == TimesheetUpload.username)
        )

        # Compile query properly
        sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        df = pd.read_sql(sql, db.engine)

        if not df.empty:
            # Normalize is_billable
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
            df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%Y-%m')

            # Aggregate data
            grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
                billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
                non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
                total_hours=pd.NamedAgg(column='hours', aggfunc='sum')
            ).reset_index()

            data = grouped.to_dict(orient='records')
        else:
            data = []

        legend = {
            "Act": "Active Days",
            "Cap": "Capacity",
            "BHrs": "Billable Hours",
            "B%": "Billable %",
            "NBHrs": "Non-Billable Hours"
        }

        return render_template('monthwise_utilization_report.html', data=data, legend=legend)

    except Exception as e:
        return f"<h1>Debug Info</h1><p>Error: {str(e)}</p><p>This is the NEW route working!</p>"
        
@reports_bp.route('/test_route_123')
def test_route_123():
    return "<h1>SUCCESS! This is working!</h1><p>Flask is running correctly.</p><p>Current time: " + str(pd.Timestamp.now()) + "</p>"
    
@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    """Employee Allocation Matrix Report."""
    return render_template('allocation_matrix.html')
    
# --- Missing Navigation Routes ---
@reports_bp.route('/reports_list')
@login_required
def reports_list():
    """Available Reports landing page."""
    return render_template('reports_list.html')

@reports_bp.route('/resource_utilization_report')
@login_required
def resource_utilization_report():
    return redirect(url_for('reports.working_utilization_report'))
    
    
@reports_bp.route('/final_utilization_solution')
@login_required
def final_utilization_solution():
    """Complete Utilization Report - Matches Template Structure"""
    
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd
        from datetime import datetime
        import calendar
        
        # Get all data with additional fields needed for template
        query = (
            db.session.query(
                TimesheetUpload.username,
                TimesheetUpload.local_date,
                TimesheetUpload.is_billable,
                TimesheetUpload.hours,
                TimesheetUpload.service_line,
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

        if df.empty:
            return render_template('monthwise_utilization_report.html', 
                                 rows=[], months=[], legend={}, 
                                 service_lines=[], projects=[], employees=[])

        # Normalize is_billable field
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
        df['month_year'] = df['local_date'].dt.strftime('%Y-%m')
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
        # Fill missing employee data
        df['employee_name'] = df['employee_name'].fillna(df['username'])
        df['service_line'] = df['service_line'].fillna('Unknown')
        df['project_name'] = df['project_name'].fillna('Unknown')
        df['doj'] = df['doj'].fillna('')
        df['doe'] = df['doe'].fillna('')
        df['reporting_manager'] = df['reporting_manager'].fillna('')
        df['designation'] = df['designation'].fillna('')
        df['location'] = df['location'].fillna('')
        
        # Get unique months sorted
        months = sorted(df['month_name'].unique())
        
        # Service line colors
        service_lines = df['service_line'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Group by employee
        employee_groups = df.groupby(['username', 'employee_name', 'service_line', 'doj', 'doe', 'reporting_manager', 'designation', 'location'])
        
        rows = []
        for (username, emp_name, service_line, doj, doe, mgr, designation, location), emp_df in employee_groups:
            
            # Calculate monthly data for this employee
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                if not month_df.empty:
                    # Billable hours by service line (for splits)
                    billable_by_service = month_df[month_df['is_billable']].groupby('service_line')['hours'].sum()
                    
                    splits = []
                    for sl, hours in billable_by_service.items():
                        if hours > 0:
                            splits.append({
                                'service_line': sl,
                                'billable': hours,
                                'color': service_line_colors.get(sl, '#999999')
                            })
                    
                    total_billable = month_df[month_df['is_billable']]['hours'].sum()
                    total_nonbillable = month_df[~month_df['is_billable']]['hours'].sum()
                    total_hours = month_df['hours'].sum()
                    
                    # Calculate billable capacity (business days * 8 hours)
                    # For now, use a simple approximation of 22 working days per month
                    billable_capacity = 22
                    
                    monthly_data[month] = {
                        'billable_hours': total_billable,
                        'nonbillable_hours': total_nonbillable,
                        'total_hours': total_hours,
                        'billable_capacity': billable_capacity,
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
                'service_line': service_line,
                'doj': doj.strftime('%Y-%m-%d') if isinstance(doj, datetime) else str(doj),
                'doe': doe.strftime('%Y-%m-%d') if isinstance(doe, datetime) else str(doe),
                'reporting_manager': mgr,
                'designation': designation,
                'location': location,
                'months': monthly_data
            })
        
        # Prepare filter options
        filter_service_lines = sorted(df['service_line'].unique())
        filter_projects = sorted(df['project_name'].dropna().unique())
        filter_employees = sorted(df['employee_name'].unique())
        
        return render_template('monthwise_utilization_report.html',
                             rows=rows,
                             months=months,
                             legend=service_line_colors,
                             service_lines=filter_service_lines,
                             projects=filter_projects,
                             employees=filter_employees)
        
    except Exception as e:
        flash(f"Error generating utilization report: {str(e)}", "danger")
        return render_template('monthwise_utilization_report.html', 
                             rows=[], months=[], legend={}, 
                             service_lines=[], projects=[], employees=[])
