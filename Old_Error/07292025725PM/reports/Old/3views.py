from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# --- Main Reports List Page ---
@reports_bp.route('/reports_list')
@login_required
def reports_list():
    """Available Reports landing page."""
    return render_template('reports_list.html')

# --- Employee Allocation Matrix ---
@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    """Employee Allocation Matrix Report."""
    return render_template('allocation_matrix.html')

# --- Employee Monthly Utilization Report ---
@reports_bp.route('/monthwise_utilization_report')
@login_required
def monthwise_utilization_report():
    """Employee Monthly Utilization Report."""
    legend = {
        "Act": "Active Days",
        "Cap": "Capacity",
        "BHrs": "Billable Hours",
        "B%": "Billable %",
        "NBHrs": "Non-Billable Hours",
        # Add service line colors or more abbreviations as needed
    }
    # --- Robust backend logic for utilization report ---
    try:
        from app import db
        from models import TimesheetUpload, Employee
        import pandas as pd
        from sqlalchemy import extract
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
        sql = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        df = pd.read_sql(sql, db.engine)
        def normalize_is_billable(val):
            if pd.isnull(val):
                return False
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return bool(val)
            val_str = str(val).strip().lower()
            return val_str in ['yes', 'true', '1', 'y']
        
        if not df.empty:
            df['is_billable'] = df['is_billable'].apply(normalize_is_billable)
            df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%Y-%m')
            
            # Aggregate data by employee and month
            grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
                billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
                non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
                total_hours=pd.NamedAgg(column='hours', aggfunc='sum'),
                entry_count=pd.NamedAgg(column='hours', aggfunc='count')
            ).reset_index()
            
            data = grouped.to_dict(orient='records')
        else:
            data = []
            
    except Exception as e:
        data = []
        flash(f"Error loading report data: {str(e)}", "danger")
    
    return render_template('monthwise_utilization_report.html', legend=legend, data=data)

# --- Projects Summary ---
@reports_bp.route('/projects_summary')
@login_required
def projects_summary():
    """Projects Summary Report."""
    return render_template('projects_list.html')

# --- Employee Skills Proficiency ---
@reports_bp.route('/skills_proficiency')
@login_required
def skills_proficiency():
    """Employee Skills Proficiency Report."""
    return render_template('skills_list.html')

# --- Employee Projects Billable Allocation ---
@reports_bp.route('/projects_billable_allocation')
@login_required
def projects_billable_allocation():
    """Employee Projects Billable Allocation Report."""
    return render_template('report_view.html')

# --- Upload Utilization (Utility in Reports) ---
@reports_bp.route('/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    """Upload Utilization Data."""
    if request.method == 'POST':
        flash('Upload Utilization not implemented.', 'info')
        return redirect(url_for('reports.upload_utilization'))
    return render_template('upload_utilization.html')

# --- Resource Utilization Dashboard (Embedded) ---
@reports_bp.route('/resource_utilization_dashboard')
@login_required
def resource_utilization_dashboard():
    """Embedded Resource Utilization Dashboard."""
    return render_template('utilities/streamlit_iframe.html')

# --- Aliases for old routes ---
@reports_bp.route('/resource_utilization_report')
@login_required
def resource_utilization_report():
    return redirect(url_for('reports.monthwise_utilization_report'))

# --- Excel Export ---
@reports_bp.route('/monthwise_utilization_report/excel')
@login_required
def utilization_excel():
    """Export utilization report to Excel."""
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
    """Email utilization report (placeholder)."""
    flash('Email export feature not implemented yet.', 'info')
    return redirect(url_for('reports.monthwise_utilization_report'))

# --- END OF REPORTS BLUEPRINT ---
