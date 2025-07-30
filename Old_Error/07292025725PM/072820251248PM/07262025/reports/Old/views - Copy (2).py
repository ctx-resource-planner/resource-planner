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
    """FINAL WORKING UTILIZATION REPORT"""
    legend = {
        "Act": "Active Days",
        "Cap": "Capacity", 
        "BHrs": "Billable Hours",
        "B%": "Billable %",
        "NBHrs": "Non-Billable Hours"
    }
    
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd

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
        else:
            data = []

    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        data = []

    return render_template('monthwise_utilization_report.html', data=data, legend=legend)