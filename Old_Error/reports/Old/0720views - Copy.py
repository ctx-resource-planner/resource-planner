###from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
###from flask_login import login_required
from sqlalchemy import extract
from io import BytesIO
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, render_template_string
from flask_login import login_required, current_user

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
                             

@reports_bp.route('/ultimate_report_2025')
@login_required
def ultimate_report_2025():
    """ULTIMATE REPORT - Brand new name to bypass all caching"""
    # Copy the exact same code from final_utilization_solution here
 
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
                             
@reports_bp.route('/simple_utilization_report')
@login_required
def simple_utilization_report():
    """Simple Working Utilization Report - Uses simple template"""
    
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
            df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%b-%Y')

            # Aggregate by employee and month
            grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
                billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
                non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
                total_hours=pd.NamedAgg(column='hours', aggfunc='sum')
            ).reset_index()

            data = grouped.to_dict(orient='records')
        else:
            data = []

    except Exception as e:
        flash(f"Error loading data: {str(e)}", "danger")
        data = []

    # Use the simple template instead
    return render_template('simple_utilization_report.html', data=data)

@reports_bp.route('/executive_utilization_dashboard')
@login_required
def executive_utilization_dashboard():
    """Executive Utilization Dashboard - Sophisticated Template"""
    
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd
        from datetime import datetime
        
        # Get all data with additional fields needed for executive template
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
        
        # Service line colors for executive presentation
        service_lines = df['service_line'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Group by employee for executive view
        employee_groups = df.groupby(['username', 'employee_name', 'service_line', 'doj', 'doe', 'reporting_manager', 'designation', 'location'])
        
        rows = []
        for (username, emp_name, service_line, doj, doe, mgr, designation, location), emp_df in employee_groups:
            
            # Calculate monthly data for this employee
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                if not month_df.empty:
                    # Billable hours by service line (for executive splits)
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
                    
                    # Executive capacity calculation (22 working days)
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
        
        # Prepare executive filter options
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
        flash(f"Error generating executive report: {str(e)}", "danger")
        return render_template('monthwise_utilization_report.html', 
                             rows=[], months=[], legend={}, 
                             service_lines=[], projects=[], employees=[])



# --- Executive Utilization Dashboard ---
@reports_bp.route('/utilization')
@login_required
def utilization():
    """Executive Utilization Dashboard - Production Ready"""
    
    # Check if user is admin
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))  # Redirect to main search page
    
    try:
        from app import db
        from models import TimesheetUpload, Employee, Project
        import pandas as pd
        from datetime import datetime
        from sqlalchemy import create_engine
        import os
        
        # Get database URL from environment or app config
        if hasattr(db.engine, 'url'):
            DATABASE_URL = str(db.engine.url)
        else:
            DATABASE_URL = os.getenv('DATABASE_URL')
        
        engine = create_engine(DATABASE_URL)
        
        # Get date range from request parameters
        start_month = request.args.get('start_month', 'Jan-2025')
        end_month = request.args.get('end_month', 'Jun-2025')
        
        sql_query = """
        SELECT 
            tu.username,
            CONCAT(tu.first_name, ' ', tu.last_name) as employee_name,
            tu.local_date,
            tu.hours,
            tu.is_billable,
            tu.project_name,
            p.service_line as project_service_line,
            COALESCE(e.service_line, 'AI') as employee_service_line,
            COALESCE(e.reporting_manager, 'Unknown') as reporting_manager,
            e.doj,
            e.doe
        FROM timesheet_uploads tu
        LEFT JOIN projects p ON tu.project_name = p.project_name
        LEFT JOIN employees e ON LOWER(tu.username) = LOWER(e.email)
        ORDER BY tu.username, tu.local_date
        """
        
        df = pd.read_sql(sql_query, engine)
        
        if df.empty:
            flash("No timesheet data found.", "warning")
            return render_template_string(EXECUTIVE_TEMPLATE, 
                                        employees=[], months=[], legend={}, 
                                        all_months=[], start_month=start_month, 
                                        end_month=end_month, total_billable_projects=0, 
                                        total_billable_resources=0)
        
        # Data processing
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
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
        
        # Clean employee names for proper sorting
        df['employee_name'] = df['employee_name'].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('ascii')
        
        # Get all unique months and sort them
        all_months = sorted(df['month_name'].unique(), key=lambda x: pd.to_datetime(x, format='%b-%Y'))
        
        # Filter by date range
        start_date = pd.to_datetime(start_month, format='%b-%Y')
        end_date = pd.to_datetime(end_month, format='%b-%Y') + pd.DateOffset(months=1) - pd.DateOffset(days=1)
        
        df_filtered = df[(df['local_date'] >= start_date) & (df['local_date'] <= end_date)]
        months = sorted(df_filtered['month_name'].unique(), key=lambda x: pd.to_datetime(x, format='%b-%Y'))
        
        # Service line colors
        service_lines = ['DTE', 'AI', 'DevOps', 'SCC', 'CloudOps']
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        legend = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Process employees
        employees = []
        for username in df_filtered['username'].unique():
            emp_data = df_filtered[df_filtered['username'] == username].iloc[0]
            
            # Monthly data
            monthly_data = {}
            for month in months:
                month_df = df_filtered[(df_filtered['username'] == username) & 
                                     (df_filtered['month_name'] == month)]
                
                if not month_df.empty:
                    billable_hours = month_df[month_df['is_billable']]['hours'].sum()
                    nonbillable_hours = month_df[~month_df['is_billable']]['hours'].sum()
                    total_hours = month_df['hours'].sum()
                    
                    # Service line splits for billable hours
                    splits = []
                    if billable_hours > 0:
                        billable_by_project = month_df[month_df['is_billable']].groupby('project_name')['hours'].sum()
                        for project, hours in billable_by_project.items():
                            project_service_line = month_df[month_df['project_name'] == project]['project_service_line'].iloc[0]
                            if pd.isna(project_service_line):
                                project_service_line = emp_data['employee_service_line']
                            
                            splits.append({
                                'service_line': project_service_line,
                                'hours': hours,
                                'color': legend.get(project_service_line, '#999999')
                            })
                    
                    # Calculate percentages
                    billable_capacity = 176  # 22 days * 8 hours
                    billable_pct = round((billable_hours / billable_capacity) * 100) if billable_capacity > 0 else 0
                    nonbillable_pct = round((nonbillable_hours / billable_capacity) * 100) if billable_capacity > 0 else 0
                    
                    monthly_data[month] = {
                        'active': total_hours > 0,
                        'billable_hours': billable_hours,
                        'billable_pct': billable_pct,
                        'nonbillable_hours': nonbillable_hours,
                        'nonbillable_pct': nonbillable_pct,
                        'splits': splits
                    }
                else:
                    monthly_data[month] = {
                        'active': False,
                        'billable_hours': 0,
                        'billable_pct': 0,
                        'nonbillable_hours': 0,
                        'nonbillable_pct': 0,
                        'splits': []
                    }
            
            # Check if employee has departed
            departed = False
            if pd.notna(emp_data['doe']):
                try:
                    doe_date = pd.to_datetime(emp_data['doe'])
                    departed = doe_date < pd.Timestamp.now()
                except:
                    departed = False
            
            employees.append({
                'name': emp_data['employee_name'],
                'bu': emp_data['employee_service_line'],
                'manager': emp_data['reporting_manager'],
                'doj': emp_data['doj'].strftime('%Y-%m-%d') if pd.notna(emp_data['doj']) else 'Unknown',
                'departed': departed,
                'monthly_data': monthly_data
            })
        
        # Sort employees alphabetically
        employees.sort(key=lambda x: x['name'])
        
        # Calculate stats - only projects/resources with billable hours in most recent month
        if months:
            most_recent_month = months[-1]
            recent_month_df = df_filtered[df_filtered['month_name'] == most_recent_month]
            total_billable_projects = len(recent_month_df[recent_month_df['is_billable']]['project_name'].unique())
            total_billable_resources = len(recent_month_df[recent_month_df['is_billable']]['username'].unique())
        else:
            total_billable_projects = 0
            total_billable_resources = 0
        
        return render_template_string(EXECUTIVE_TEMPLATE,
                                    employees=employees,
                                    months=months,
                                    legend=legend,
                                    all_months=all_months,
                                    start_month=start_month,
                                    end_month=end_month,
                                    total_billable_projects=total_billable_projects,
                                    total_billable_resources=total_billable_resources)
        
    except Exception as e:
        flash(f"Error generating utilization dashboard: {str(e)}", "danger")
        return render_template_string(EXECUTIVE_TEMPLATE,
                                    employees=[], months=[], legend={},
                                    all_months=[], start_month='Jan-2025',
                                    end_month='Jun-2025', total_billable_projects=0,
                                    total_billable_resources=0)


# Embedded HTML template for the executive dashboard
EXECUTIVE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Utilization Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/fixedcolumns/4.3.0/css/fixedColumns.bootstrap5.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        
        .main-container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 30px;
            margin: 0 auto;
            max-width: 100%;
            backdrop-filter: blur(10px);
        }
        
        .header-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .header-section h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.3);
        }
        
        .stat-number {
            font-size: 3rem;
            font-weight: 700;
            margin: 10px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .stat-label {
            font-size: 1.1rem;
            opacity: 0.9;
            font-weight: 500;
        }
        
        .control-panel {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 15px;
            margin-bottom: 30px;
            border: 1px solid #e9ecef;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
        }
        
        .legend-enhanced {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }
        
        .legend-badge {
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }
        
        .table-container {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .table {
            margin: 0;
            font-size: 0.9rem;
        }
        
        .table thead th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 8px;
            font-weight: 600;
            text-align: center;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        
        .table tbody tr:hover {
            background-color: #f8f9fa;
        }
        
        .table td {
            padding: 12px 8px;
            vertical-align: middle;
            border-top: 1px solid #e9ecef;
        }
        
        .employee-name {
            font-weight: 600;
            color: #2c3e50;
        }
        
        .employee-name.departed {
            color: #e74c3c;
            font-weight: 700;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 5px;
        }
        
        .status-active { background-color: #28a745; }
        .status-inactive { background-color: #6c757d; }
        
        .hours-cell {
            text-align: center;
            font-weight: 600;
        }
        
        .service-badge {
            display: inline-block;
            color: white;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            margin: 1px;
            text-shadow: 1px 1px 1px rgba(0,0,0,0.3);
        }
        
        .btn-enhanced {
            border-radius: 25px;
            padding: 10px 25px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            border: none;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .btn-enhanced:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .form-select, .form-control {
            border-radius: 10px;
            border: 2px solid #e9ecef;
            padding: 10px 15px;
            transition: border-color 0.3s ease;
        }
        
        .form-select:focus, .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        
        .form-label {
            color: #495057;
            margin-bottom: 8px;
        }
        
        @media (max-width: 768px) {
            .main-container {
                padding: 15px;
                margin: 10px;
            }
            
            .header-section h1 {
                font-size: 1.8rem;
            }
            
            .stat-number {
                font-size: 2rem;
            }
            
            .control-panel {
                padding: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="main-container">
        <!-- Header -->
        <div class="header-section">
            <h1>📊 Utilization Dashboard</h1>
        </div>
        
        <!-- Stats Cards -->
        <div class="stats-container">
            <div class="stat-card">
                <div class="stat-label">📋 Total Billable Projects</div>
                <div class="stat-number">{{ total_billable_projects }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">👥 Total Billable Resources</div>
                <div class="stat-number">{{ total_billable_resources }}</div>
            </div>
        </div>
        
        <!-- Enhanced Control Panel -->
        <div class="control-panel">
            <div class="row align-items-center">
                <div class="col-md-2">
                    <label class="form-label fw-bold">📅 Start Month:</label>
                    <select id="startMonth" class="form-select">
                        {% for month in all_months %}
                        <option value="{{ month }}" {% if month == start_month %}selected{% endif %}>{{ month }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label fw-bold">📅 End Month:</label>
                    <select id="endMonth" class="form-select">
                        {% for month in all_months %}
                        <option value="{{ month }}" {% if month == end_month %}selected{% endif %}>{{ month }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-4">
                    <div class="legend-enhanced">
                        <label class="fw-bold">🏢 Business Units:</label><br>
                        {% for bu, color in legend.items() %}
                            <span class="legend-badge" style="background:{{ color }};">{{ bu }}</span>
                        {% endfor %}
                    </div>
                </div>
                <div class="col-md-4 text-end">
                    <button class="btn btn-success btn-enhanced" onclick="exportToExcel()">📊 Excel</button>
                    <button class="btn btn-primary btn-enhanced ms-1" onclick="emailReport()">📧 Email</button>
                </div>
            </div>
        </div>
        
        <!-- Table -->
        <div class="table-container">
            <table id="utilizationTable" class="table table-striped table-hover">
                <thead>
                    <tr>
                        <th>Employee</th>
                        <th>BU</th>
                        <th>Manager</th>
                        <th>DOJ</th>
                        {% for month in months %}
                            <th colspan="5" style="text-align: center; border-left: 2px solid #fff;">{{ month }}</th>
                        {% endfor %}
                    </tr>
                    <tr style="background: linear-gradient(135deg, #5a67d8 0%, #667eea 100%);">
                        <th></th>
                        <th></th>
                        <th></th>
                        <th></th>
                        {% for month in months %}
                            <th style="font-size: 0.8rem; padding: 8px 4px;">Act</th>
                            <th style="font-size: 0.8rem; padding: 8px 4px;">B-H</th>
                            <th style="font-size: 0.8rem; padding: 8px 4px;">B%</th>
                            <th style="font-size: 0.8rem; padding: 8px 4px;">NB-H</th>
                            <th style="font-size: 0.8rem; padding: 8px 4px; border-right: 2px solid #fff;">NB%</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for employee in employees %}
                    <tr>
                        <td class="employee-name {% if employee.departed %}departed{% endif %}">
                            {{ employee.name }}
                        </td>
                        <td>{{ employee.bu }}</td>
                        <td>{{ employee.manager }}</td>
                        <td>{{ employee.doj }}</td>
                        {% for month in months %}
                            {% set month_data = employee.monthly_data.get(month, {}) %}
                            <td class="text-center">
                                <span class="status-dot {% if month_data.active %}status-active{% else %}status-inactive{% endif %}"></span>
                            </td>
                            <td class="hours-cell">
                                {% if month_data.billable_hours > 0 %}
                                    {{ "%.0f"|format(month_data.billable_hours) }}
                                    {% for split in month_data.splits %}
                                        <span class="service-badge" style="background-color: {{ split.color }};">
                                            {{ split.service_line }}: {{ "%.0f"|format(split.hours) }}
                                        </span>
                                    {% endfor %}
                                {% else %}
                                    0
                                {% endif %}
                            </td>
                            <td class="hours-cell">{{ month_data.billable_pct }}%</td>
                            <td class="hours-cell">{{ "%.0f"|format(month_data.nonbillable_hours) if month_data.nonbillable_hours > 0 else "0" }}</td>
                            <td class="hours-cell" style="border-right: 2px solid #e9ecef;">{{ month_data.nonbillable_pct }}%</td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
    <script src="https://cdn.datatables.net/fixedcolumns/4.3.0/js/dataTables.fixedColumns.min.js"></script>
    
    <script>
        $(document).ready(function() {
            var table = $('#utilizationTable').DataTable({
                "paging": false,
                "info": false,
                "searching": true,
                "ordering": true,
                "scrollX": true,
                "order": [[ 0, "asc" ]],
                "fixedColumns": {
                    "leftColumns": 4
                },
                "columnDefs": [
                    { "orderable": true, "targets": [0, 1, 2, 3] },
                    { "orderable": false, "targets": "_all" }
                ]
            });
            
            $('#startMonth, #endMonth').on('change', function() {
                var startMonth = $('#startMonth').val();
                var endMonth = $('#endMonth').val();
                window.location.href = '/reports/utilization?start_month=' + startMonth + '&end_month=' + endMonth;
            });
        });
        
        function exportToExcel() {
            alert('Excel export functionality will be implemented soon.');
        }
        
        function emailReport() {
            alert('Email report functionality will be implemented soon.');
        }
    </script>
</body>
</html>
"""