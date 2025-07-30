from flask import Blueprint, render_template, request, send_file, flash
from flask_login import login_required
from sqlalchemy import extract
from app import db
import pandas as pd
from io import BytesIO
# Import your models here
from models import TimesheetUpload, Employee

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# --- Utilization Report Main Route ---
@reports_bp.route('/monthwise_utilization_report')
@login_required
def monthwise_utilization_report():
    selected_month = request.args.get('month')
    selected_employee = request.args.get('employee')

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
    if selected_month:
        year, month = map(int, selected_month.split('-'))
        query = query.filter(
            extract('year', TimesheetUpload.local_date) == year,
            extract('month', TimesheetUpload.local_date) == month
        )
    if selected_employee:
        query = query.filter(TimesheetUpload.username == selected_employee)

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

    df['is_billable'] = df['is_billable'].apply(normalize_is_billable)
    df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%Y-%m')

    grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
        billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
        non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
        total_hours=pd.NamedAgg(column='hours', aggfunc='sum'),
        entry_count=pd.NamedAgg(column='hours', aggfunc='count')
    ).reset_index()

    legend = {
        "Act": "Active Days",
        "Cap": "Capacity",
        "BHrs": "Billable Hours",
        "B%": "Billable %",
        "NBHrs": "Non-Billable Hours"
        # Add service line colors if needed
    }

    return render_template(
        'monthwise_utilization_report.html',
        data=grouped.to_dict(orient='records'),
        legend=legend
    )

# --- Resource Utilization Report (Alias) ---
@reports_bp.route('/resource_utilization_report')
@login_required
def resource_utilization_report():
    return monthwise_utilization_report()

# --- Excel Export ---
@reports_bp.route('/monthwise_utilization_report/excel')
@login_required
def utilization_excel():
    selected_month = request.args.get('month')
    selected_employee = request.args.get('employee')
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
    if selected_month:
        year, month = map(int, selected_month.split('-'))
        query = query.filter(
            extract('year', TimesheetUpload.local_date) == year,
            extract('month', TimesheetUpload.local_date) == month
        )
    if selected_employee:
        query = query.filter(TimesheetUpload.username == selected_employee)
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
    df['is_billable'] = df['is_billable'].apply(normalize_is_billable)
    df['month_year'] = pd.to_datetime(df['local_date']).dt.strftime('%Y-%m')
    grouped = df.groupby(['username', 'employee_name', 'month_year']).agg(
        billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[df.loc[x.index, 'is_billable']].sum()),
        non_billable_hours=pd.NamedAgg(column='hours', aggfunc=lambda x: x[~df.loc[x.index, 'is_billable']].sum()),
        total_hours=pd.NamedAgg(column='hours', aggfunc='sum'),
        entry_count=pd.NamedAgg(column='hours', aggfunc='count')
    ).reset_index()
    output = BytesIO()
    grouped.to_excel(output, index=False)
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='utilization_report.xlsx'
    )

# --- Email Export (Placeholder) ---
@reports_bp.route('/monthwise_utilization_report/email')
@login_required
def utilization_email():
    flash("Email feature not implemented yet.", "info")
    return "Email feature not implemented yet.", 501

# --- Allocation Matrix (Placeholder) ---
@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    # TODO: Implement actual allocation matrix logic and template
    return render_template('allocation_matrix.html')

# Register this blueprint in your main app:
# from reports.views import reports_bp
# app.register_blueprint(reports_bp)


@reports_bp.route('/reports_list')
@login_required
def reports_list():
    # Replace with your actual reports list logic or template
    return render_template('reports_list.html')