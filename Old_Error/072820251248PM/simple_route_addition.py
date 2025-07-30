# Add this route to your reports/views.py file

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
