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
from app import app  # Add this import

print("VIEWS.PY LOADED")

reports_bp = Blueprint('reports', __name__, template_folder='templates')

def get_us_business_days_and_hours(year, month, doj=None, doe=None):
    """Calculate US business days and hours for a given month, considering DOJ/DOE"""
    import calendar
    from datetime import datetime, date
    import holidays
    
    try:
        # US holidays
        us_holidays = holidays.US(years=year)
        
        # Get all days in the month
        _, last_day = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        
        # Handle DOJ (Date of Joining) - employee starts mid-month
        if doj and isinstance(doj, (date, datetime)):
            if hasattr(doj, 'date'):
                doj = doj.date()
            # FIXED: Only adjust if DOJ is in this specific month
            if doj.year == year and doj.month == month and doj.day <= last_day:
                month_start = max(month_start, doj)
        
        # Handle DOE (Date of Exit) - employee leaves mid-month  
        if doe and isinstance(doe, (date, datetime)):
            if hasattr(doe, 'date'):
                doe = doe.date()
            # FIXED: Only adjust if DOE is in this specific month
            if doe.year == year and doe.month == month and doe.day <= last_day:
                month_end = min(month_end, doe)
        
        # Count business days (Monday=0, Sunday=6)
        business_days = 0
        current_date = month_start
        
        while current_date <= month_end:
            # Check if it's a weekday (Mon-Fri) and not a holiday
            if current_date.weekday() < 5 and current_date not in us_holidays:
                business_days += 1
            # FIXED: Use timedelta to avoid date arithmetic errors
            from datetime import timedelta
            current_date = current_date + timedelta(days=1)
        
        # Convert to hours (8 hours per business day)
        business_hours = business_days * 8
        
        return business_days, business_hours
        
    except Exception as e:
        print(f"Error in date calculation: {e}")
        # Fallback to standard month
        return 22, 176
    

# --- Reports List Route for Navbar ---
@reports_bp.route('/reports', methods=['GET'])
@login_required
def reports_list():
    return render_template('reports_list.html', reports=REPORTS)

@reports_bp.route('/test-redirect')
@login_required
def test_redirect():
    """Test route to verify redirects work"""
    from flask import request
    print(f"🧪 TEST ROUTE CALLED with args: {dict(request.args)}")
    return f"Test successful! Args: {dict(request.args)}"
    
# --- NEW: Executive Utilization Dashboard ---
@reports_bp.route('/executive-utilization-dashboard')
@login_required
def executive_utilization_dashboard():
    """Executive Utilization Dashboard - WITH PROPER CAPACITY CALCULATION"""
    try:
        import pandas as pd
        from datetime import datetime
        from flask import request
        from app import db
        
        # Get filter parameters
        start_month = request.args.get('start_month')
        end_month = request.args.get('end_month')

        # DEBUG: Print received parameters
        print(f"🔍 RECEIVED PARAMETERS: start_month={start_month}, end_month={end_month}")
        print(f"🔍 REQUEST ARGS: {dict(request.args)}")
                
        # Get data
        sql_query = "SELECT * FROM dashboard_utilization_data ORDER BY username, local_date"
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            return render_template_string(EXECUTIVE_TEMPLATE, rows=[], months=[], legend={}, 
                                 total_billable_projects=0, total_billable_resources=0, timestamp='Now',
                                 start_month='', end_month='', all_months=[])

        # Clean data
        df['is_billable'] = df['is_billable'].fillna(False)
        df['is_billable'] = df['is_billable'].astype(str).str.lower().isin(['true', '1', 'yes', 'y'])
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
        # Convert DOJ/DOE to proper datetime
        df['doj'] = pd.to_datetime(df['doj'], errors='coerce')
        df['doe'] = pd.to_datetime(df['doe'], errors='coerce')
        
        # Fill nulls
        df = df.fillna({
            'employee_name': df['username'],
            'employee_service_line': 'Unknown',
            'service_line': 'Unknown',
            'project_name': 'Unknown',
            'reporting_manager': 'Unknown',
            'designation': 'Unknown',
            'location': 'Unknown'
        })
        
        # Colors - ADD AI business unit
        service_lines = list(df['service_line'].unique())
        # Ensure AI is always included in legend
        if 'AI' not in service_lines:
            service_lines.append('AI')

        #colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#FF9F43', '#6C5CE7']
        #legend = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        colors = ['#FF6B6B', '#9c9567', '#3e706d', '#d1a506', '#094c99', '#038523', '#98D8C8', '#F7DC6F', '#FF9F43', '#6C5CE7']
        legend = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Sort months chronologically
        month_dates = []
        for month_str in df['month_name'].unique():
            try:
                month_date = datetime.strptime(month_str, '%b-%Y')
                month_dates.append((month_date, month_str))
            except:
                pass
        
        all_months = [month_str for _, month_str in sorted(month_dates)]
        
        # Filter months based on start/end selection
        if start_month and end_month and start_month in all_months and end_month in all_months:
            start_idx = all_months.index(start_month)
            end_idx = all_months.index(end_month)
            months = all_months[start_idx:end_idx+1]
        else:
            months = all_months
            start_month = all_months[0] if all_months else ''
            end_month = all_months[-1] if all_months else ''
        
        # Process each employee
        rows = []
        for username in df['username'].unique():
            emp_df = df[df['username'] == username]
            emp_info = emp_df.iloc[0]
            
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                # FIXED: Calculate proper billable capacity using US business days
                try:
                    month_date = datetime.strptime(month, '%b-%Y')
                    year, month_num = month_date.year, month_date.month
                    
                    # Get employee DOJ/DOE for this month
                    emp_doj = emp_info['doj'] if pd.notna(emp_info['doj']) else None
                    emp_doe = emp_info['doe'] if pd.notna(emp_info['doe']) else None
                    
                    business_days, business_hours = get_us_business_days_and_hours(
                        year, month_num, emp_doj, emp_doe
                    )
                    
                except Exception as e:
                    print(f"Error calculating capacity for {username} in {month}: {e}")
                    business_days, business_hours = 22, 176  # Fallback
                
                if not month_df.empty:
                    billable_hours = month_df[month_df['is_billable']]['hours'].sum()
                    nonbillable_hours = month_df[~month_df['is_billable']]['hours'].sum()
                    
                    # Create splits
                    splits = []
                    if billable_hours > 0:
                        billable_df = month_df[month_df['is_billable']]
                        for sl in billable_df['service_line'].unique():
                            sl_hours = billable_df[billable_df['service_line'] == sl]['hours'].sum()
                            if sl_hours > 0:
                                splits.append({
                                    'service_line': sl,
                                    'hours': sl_hours,
                                    'color': legend.get(sl, '#999')
                                })
                    
                    # FIXED: Calculate percentages using hours, not days
                    billable_percentage = (billable_hours / business_hours * 100) if business_hours > 0 else 0
                    nonbillable_percentage = (nonbillable_hours / business_hours * 100) if business_hours > 0 else 0
                    
                    monthly_data[month] = {
                        'billable_hours': billable_hours,
                        'nonbillable_hours': nonbillable_hours,
                        'total_hours': billable_hours + nonbillable_hours,
                        'billable_capacity_days': business_days,
                        'billable_capacity_hours': business_hours,
                        'billable_percentage': billable_percentage,
                        'nonbillable_percentage': nonbillable_percentage,
                        'splits': splits
                    }
                else:
                    monthly_data[month] = {
                        'billable_hours': 0,
                        'nonbillable_hours': 0,
                        'total_hours': 0,
                        'billable_capacity_days': business_days,
                        'billable_capacity_hours': business_hours,
                        'billable_percentage': 0,
                        'nonbillable_percentage': 0,
                        'splits': []
                    }
            
            rows.append({
                'username': username,
                'name': emp_info['employee_name'],
                'service_line': emp_info['employee_service_line'],
                'doj': str(emp_info['doj'])[:10] if pd.notna(emp_info['doj']) else 'N/A',
                'doe': str(emp_info['doe'])[:10] if pd.notna(emp_info['doe']) else None,
                'reporting_manager': emp_info['reporting_manager'],
                'months': monthly_data
            })
        
        # Stats
        total_billable_projects = len(df[df['is_billable']]['project_name'].unique())
        total_billable_resources = len(df[df['is_billable']]['username'].unique())
        
        return render_template_string(EXECUTIVE_TEMPLATE,
                             rows=rows, months=months, legend=legend,
                             all_months=all_months, start_month=start_month, end_month=end_month,
                             total_billable_projects=total_billable_projects,
                             total_billable_resources=total_billable_resources,
                             timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'))
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template_string(EXECUTIVE_TEMPLATE, rows=[], months=[], legend={}, 
                             total_billable_projects=0, total_billable_resources=0, timestamp='Now',
                             all_months=[], start_month='', end_month='')
                             
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
        # Calculate stats - FIXED: Only count projects with billable hours in the most recent month
        if months:
            most_recent_month = months[-1]  # Last month in the sorted list
            recent_month_data = df[df['month_name'] == most_recent_month]
            
            # Count projects that have billable hours in the most recent month
            total_billable_projects = len(recent_month_data[
                (recent_month_data['is_billable']) & 
                (recent_month_data['hours'] > 0)
            ]['project_name'].unique())
            
            # Count resources that have billable hours in the most recent month
            total_billable_resources = len(recent_month_data[
                (recent_month_data['is_billable']) & 
                (recent_month_data['hours'] > 0)
            ]['username'].unique())
        else:
            total_billable_projects = 0
            total_billable_resources = 0
        
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

@app.route('/executive-utilization-dashboard/export')  # Use app, not reports_bp
@login_required
def export_executive_dashboard():
    """Export Executive Dashboard to Excel"""
    try:
        import pandas as pd
        from datetime import datetime
        from flask import request
        from io import BytesIO
        from flask import send_file
        from app import db
        
        # Get filter parameters
        start_month = request.args.get('start_month')
        end_month = request.args.get('end_month')
        
        # Get the same data as the dashboard
        sql_query = "SELECT * FROM dashboard_utilization_data ORDER BY username, local_date"
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            flash("No data to export.", "warning")
            return redirect(url_for('reports.executive_utilization_dashboard'))
        
        # Process data (same logic as dashboard)
        df['is_billable'] = df['is_billable'].fillna(False)
        df['is_billable'] = df['is_billable'].astype(str).str.lower().isin(['true', '1', 'yes', 'y'])
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
        # Fill nulls
        df = df.fillna({
            'employee_name': df['username'],
            'employee_service_line': 'Unknown',
            'service_line': 'Unknown',
            'project_name': 'Unknown',
            'reporting_manager': 'Unknown'
        })
        
        # Sort months chronologically
        month_dates = []
        for month_str in df['month_name'].unique():
            try:
                month_date = datetime.strptime(month_str, '%b-%Y')
                month_dates.append((month_date, month_str))
            except:
                pass
        
        all_months = [month_str for _, month_str in sorted(month_dates)]
        
        # Filter months if specified
        if start_month and end_month and start_month in all_months and end_month in all_months:
            start_idx = all_months.index(start_month)
            end_idx = all_months.index(end_month)
            months = all_months[start_idx:end_idx+1]
        else:
            months = all_months
        
        # Prepare export data
        export_data = []
        for username in df['username'].unique():
            emp_df = df[df['username'] == username]
            emp_info = emp_df.iloc[0]
            
            row_data = {
                'Employee': emp_info['employee_name'],
                'Business Unit': emp_info['employee_service_line'],
                'Manager': emp_info['reporting_manager'],
                'DOJ': str(emp_info['doj'])[:10] if pd.notna(emp_info['doj']) else 'N/A',
                'DOE': str(emp_info['doe'])[:10] if pd.notna(emp_info['doe']) else 'Active'
            }
            
            # Add monthly data
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                if not month_df.empty:
                    billable_hours = month_df[month_df['is_billable']]['hours'].sum()
                    nonbillable_hours = month_df[~month_df['is_billable']]['hours'].sum()
                    
                    # Calculate capacity
                    try:
                        month_date = datetime.strptime(month, '%b-%Y')
                        year, month_num = month_date.year, month_date.month
                        emp_doj = emp_info['doj'] if pd.notna(emp_info['doj']) else None
                        emp_doe = emp_info['doe'] if pd.notna(emp_info['doe']) else None
                        business_days, business_hours = get_us_business_days_and_hours(year, month_num, emp_doj, emp_doe)
                    except:
                        business_hours = 176
                    
                    billable_percentage = (billable_hours / business_hours * 100) if business_hours > 0 else 0
                    nonbillable_percentage = (nonbillable_hours / business_hours * 100) if business_hours > 0 else 0
                    
                    row_data[f'{month} - Capacity (hrs)'] = business_hours
                    row_data[f'{month} - Billable Hours'] = billable_hours
                    row_data[f'{month} - Billable %'] = f"{billable_percentage:.1f}%"
                    row_data[f'{month} - Non-Billable Hours'] = nonbillable_hours
                    row_data[f'{month} - Non-Billable %'] = f"{nonbillable_percentage:.1f}%"
                else:
                    row_data[f'{month} - Capacity (hrs)'] = 0
                    row_data[f'{month} - Billable Hours'] = 0
                    row_data[f'{month} - Billable %'] = "0.0%"
                    row_data[f'{month} - Non-Billable Hours'] = 0
                    row_data[f'{month} - Non-Billable %'] = "0.0%"
            
            export_data.append(row_data)
        
        # Create Excel file with enhanced formatting
            df_export = pd.DataFrame(export_data)
            output = BytesIO()

            writer = pd.ExcelWriter(output, engine='openpyxl')
            df_export.to_excel(writer, index=False, sheet_name='Executive Utilization Dashboard')

            # Get the workbook and worksheet for formatting
            workbook = writer.book
            worksheet = writer.sheets['Executive Utilization Dashboard']

            # Define styles
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            percentage_fill = PatternFill(start_color="E8F4FD", end_color="E8F4FD", fill_type="solid")
            hours_fill = PatternFill(start_color="F0F8F0", end_color="F0F8F0", fill_type="solid")
            border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                            top=Side(style='thin'), bottom=Side(style='thin'))

            # Format headers
            for col_num, column_title in enumerate(df_export.columns, 1):
                cell = worksheet.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border

            # Format data cells
            for row_num in range(2, len(df_export) + 2):
                for col_num, column_title in enumerate(df_export.columns, 1):
                    cell = worksheet.cell(row=row_num, column=col_num)
                    cell.border = border
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    
                    # Color code based on column type
                    if "%" in column_title:
                        cell.fill = percentage_fill
                    elif "Hours" in column_title:
                        cell.fill = hours_fill

            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 20)  # Cap at 20 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width

            writer.close()
            output.seek(0)
        
        # Generate filename
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        month_range = f"{start_month}_to_{end_month}" if start_month and end_month else "all_months"
        fname = f"executive_utilization_dashboard_{month_range}_{ts}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=fname
        )
        
    except Exception as e:
        print(f"❌ Export Error: {str(e)}")
        flash(f"Error generating Excel file: {str(e)}", "danger")
        return redirect(url_for('reports.executive_utilization_dashboard'))


@app.route('/executive-utilization-dashboard/email', methods=['POST'])  # Use app, not reports_bp
@login_required
def email_executive_dashboard():
    """Email Executive Dashboard Report"""
    try:
        from flask_mail import Message
        from app import mail
        import pandas as pd
        from datetime import datetime
        from flask import request
        from io import BytesIO
        from app import db
        
        recipient_email = request.form.get('recipient_email')
        start_month = request.form.get('start_month')
        end_month = request.form.get('end_month')
        
        if not recipient_email:
            flash("Recipient email required.", "warning")
            return redirect(url_for('reports.executive_utilization_dashboard'))
        
        # Get the same data as export (reuse the logic)
        # ... (same data processing as export function above)
        
        # For brevity, I'll create a simpler version - you can expand this
        sql_query = "SELECT * FROM dashboard_utilization_data ORDER BY username, local_date"
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            flash("No data to email.", "warning")
            return redirect(url_for('reports.executive_utilization_dashboard'))
        
        # Create a simple summary for email
        summary_data = []
        for username in df['username'].unique():
            emp_df = df[df['username'] == username]
            emp_info = emp_df.iloc[0]
            
            total_billable = emp_df[emp_df['is_billable'].astype(str).str.lower().isin(['true', '1', 'yes', 'y'])]['hours'].sum()
            total_nonbillable = emp_df[~emp_df['is_billable'].astype(str).str.lower().isin(['true', '1', 'yes', 'y'])]['hours'].sum()
            
            summary_data.append({
                'Employee': emp_info['employee_name'],
                'Business Unit': emp_info['employee_service_line'],
                'Total Billable Hours': total_billable,
                'Total Non-Billable Hours': total_nonbillable,
                'Manager': emp_info['reporting_manager']
            })
        
        df_summary = pd.DataFrame(summary_data)
        output = BytesIO()
        
        writer = pd.ExcelWriter(output, engine='openpyxl')
        df_summary.to_excel(writer, index=False, sheet_name='Utilization Summary')
        writer.close()
        output.seek(0)
        
        # Send email
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"executive_utilization_summary_{ts}.xlsx"
        
        msg = Message("Executive Utilization Dashboard Report",
                      sender=app.config['MAIL_DEFAULT_SENDER'],
                      recipients=[recipient_email])
        msg.body = f"Please find the attached Executive Utilization Dashboard report.\n\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        msg.attach(filename=fname,
                   content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                   data=output.read())
        
        mail.send(msg)
        flash(f"Report sent to {recipient_email}.", "success")
        
    except Exception as e:
        print(f"❌ Email Error: {str(e)}")
        flash(f"Failed to send email report. Error: {str(e)}", "danger")
    
    return redirect(url_for('reports.executive_utilization_dashboard'))
    
    
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
EXECUTIVE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Utilization Dashboard</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/fixedcolumns/4.3.0/css/fixedColumns.dataTables.min.css">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            margin: 0;
            padding: 0;
        }
        
        .container-fluid {
            max-width: 100% !important;
            padding: 10px !important;
            background: transparent;
        }
        
        /* Enhanced Header */
        .dashboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .dashboard-header h4 {
            margin: 0;
            font-weight: 600;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        /* Enhanced Stats Cards */
        .stats-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .stats-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 35px rgba(102, 126, 234, 0.4);
        }
        
        .stats-card h6 {
            margin: 0 0 10px 0;
            opacity: 0.9;
            font-size: 0.9em;
        }
        
        .stats-card h4 {
            margin: 0;
            font-size: 2.2em;
            font-weight: 700;
        }
        
        /* Enhanced Control Panel */
        .control-panel {
            background: white;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            border: 1px solid #e9ecef;
        }
        
        .form-select, .form-control {
            border-radius: 8px;
            border: 2px solid #e9ecef;
            transition: border-color 0.3s ease;
        }
        
        .form-select:focus, .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        
        /* Enhanced Legend */
        .legend-enhanced {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 8px;
            padding: 12px;
            border: 1px solid #dee2e6;
        }
        
        .legend-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            color: white;
            font-size: 0.75em;
            margin-right: 6px;
            margin-bottom: 4px;
            font-weight: 600;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        /* Enhanced Buttons */
        .btn-enhanced {
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        
        .btn-enhanced:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        }
        
        /* Enhanced Table with Fixed Columns */
        .table-container {
            background: white;
            border-radius: 12px;
            overflow: visible;  /* CHANGED: Allow overflow for DataTables */
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
            border: 1px solid #e9ecef;
            /* REMOVED: max-height restriction */
        }
        
        .table {
            margin: 0;
            font-size: 0.75em;
            width: 100%;
        }
        
        .table thead th {
            background: linear-gradient(135deg, #495057 0%, #6c757d 100%);
            color: white;
            border: none;
            font-weight: 600;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
            position: sticky;
            top: 0;
            z-index: 10;
        }
        
        .table tbody tr:hover {
            background-color: #f8f9fa;
            transition: background-color 0.2s ease;
        }
        
        /* Fixed Columns Styling */
        /* Fixed Columns Styling */
        .employee-name, 
        .employee-bu,
        th.employee-name,
        th.employee-bu,
        td.employee-name, 
        td.employee-bu {
            text-align: left !important;
            font-weight: 600 !important;
            background: #D0D0D0 !important;
            color: #000000 !important;
            position: sticky !important;
            z-index: 5 !important;
            border-right: 2px solid #dee2e6 !important;
        }

        .employee-name {
            left: 0;
            min-width: 140px !important;
        }

        .employee-bu {
            left: 140px;
            min-width: 80px !important;
        }
        
        .employee-departed {
            color: #dc3545 !important;
            opacity: 0.7;
            text-decoration: line-through;
        }
        
        /* Enhanced Service Splits */
        .service-split {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            color: white;
            margin-right: 2px;
            margin-bottom: 2px;
            font-weight: 600;
            font-size: 0.7em;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }
        
        /* Enhanced Active Dots */
        .active-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }
        
        .active-green { 
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }
        
        .active-gray { 
            background: linear-gradient(135deg, #6c757d 0%, #adb5bd 100%);
        }
        
        /* Enhanced Footer */
        .dashboard-footer {
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            text-align: center;
            border: 1px solid #e9ecef;
        }
        
        .month-header {
            background-color: #495057 !important;
            color: white !important;
            font-size: 0.7em;
            padding: 2px !important;
            text-align: center;
        }
        
        .sub-header {
            background-color: #6c757d !important;
            color: white !important;
            font-size: 0.6em;
            padding: 1px !important;
            text-align: center;
            min-width: 45px;
        }
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .stats-card {
                margin-bottom: 10px;
            }
            .control-panel {
                padding: 15px;
            }
        }
        /* Month Separator */
        .month-separator {
            border-left: 3px solid #495057 !important;
        }
    </style>
</head>
<body>
<div class="container-fluid">
    <!-- Enhanced Header -->
    <div class="dashboard-header">
        <h4>🎯 Utilization Dashboard</h4>
    </div>
    
    <!-- Enhanced Stats Cards -->
    <div class="row mb-3">
        <div class="col-md-6">
            <div class="stats-card">
                <h6>📊 Total Billable Projects</h6>
                <h4>{{ total_billable_projects|default(0) }}</h4>
            </div>
        </div>
        <div class="col-md-6">
            <div class="stats-card">
                <h6>👥 Total Billable Resources</h6>
                <h4>{{ total_billable_resources|default(0) }}</h4>
            </div>
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
            <div class="col-md-3">
                <div class="legend-enhanced">
                    <label class="fw-bold">🏢 Business Units:</label><br>
                    {% for bu, color in legend.items() %}
                        <span class="legend-badge" style="background:{{ color }};">{{ bu }}</span>
                    {% endfor %}
                </div>
            </div>
            <div class="col-md-2">
                <label class="form-label fw-bold">🔍 Search:</label>
                <input type="text" id="globalSearch" class="form-control" placeholder="Search employees..." />
            </div>
            <div class="col-md-3 text-end">
                <button class="btn btn-success btn-enhanced" onclick="exportToExcel()">📊 Excel</button>
                <button class="btn btn-primary btn-enhanced ms-1" onclick="emailReport()">📧 Email</button>
                <a href="{{ url_for('reports.reports_list') }}" class="btn btn-outline-secondary btn-enhanced ms-1">🔙 Back</a>
            </div>
        </div>
    </div>

    <!-- Enhanced Table Container -->
    <!-- Enhanced Table Container -->
        <div class="table-container">
            <table id="utilizationTable" class="table table-bordered table-striped table-sm">
                <thead>
                    <tr>
                        <th rowspan="2" class="employee-name">Employee</th>
                        <th rowspan="2" class="employee-bu">BU</th>
                        <th rowspan="2">Manager</th>
                        <th rowspan="2">DOJ</th>
                        {% for month in months %}
                        <th colspan="6" class="month-header {% if not loop.first %}month-separator{% endif %}">{{ month }}</th>
                        {% endfor %}
                    </tr>
                    <tr>
                        {% for month in months %}
                        <th class="sub-header {% if not loop.first %}month-separator{% endif %}">Act</th>
                        <th class="sub-header">BC</th>
                        <th class="sub-header">B-H</th>
                        <th class="sub-header">B%</th>
                        <th class="sub-header">NB-H</th>
                        <th class="sub-header">NB%</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                {% for row in rows %}
                    <tr>
                        <td class="employee-name {% if row.doe %}employee-departed{% endif %}">{{ row.name }}</td>
                        <td class="employee-bu"><span class="legend-badge" style="background:{{ legend.get(row.service_line, '#999') }};">{{ row.service_line }}</span></td>
                        <td>{{ row.reporting_manager[:10] if row.reporting_manager else 'N/A' }}</td>
                        <td>{{ row.doj }}</td>
                        {% for month in months %}
                        {% set month_data = row.months.get(month, {}) %}
                        <td {% if not loop.first %}class="month-separator"{% endif %}>
                            <span class="active-dot {% if month_data.get('total_hours', 0) > 0 %}active-green{% else %}active-gray{% endif %}"></span>
                        </td>
                        <td><b>{{ "%.0f"|format(month_data.get('billable_capacity_hours', 0)) }}</b></td>
                        <td>
                            {% if month_data.get('splits', []) and month_data.splits|length > 1 %}
                                {% for split in month_data.splits %}
                                    <span class="service-split" style="background-color: {{ split.color }}">
                                        {{ "%.0f"|format(split.hours) }}
                                    </span>
                                {% endfor %}
                                <br><small><b>{{ "%.0f"|format(month_data.get('billable_hours', 0)) }}</b></small>
                            {% else %}
                                <b>{{ "%.0f"|format(month_data.get('billable_hours', 0)) }}</b>
                            {% endif %}
                        </td>
                        <td><b>{{ "%.0f"|format(month_data.get('billable_percentage', 0)) }}%</b></td>
                        <td><b>{{ "%.0f"|format(month_data.get('nonbillable_hours', 0)) }}</b></td>
                        <td><b>{{ "%.0f"|format(month_data.get('nonbillable_percentage', 0)) }}%</b></td>
                        {% endfor %}
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    
    <!-- Enhanced Footer -->
    <div class="dashboard-footer">
        <small>
            <strong>📈 Employees:</strong> {{ rows|length }} | 
            <strong>📝 Abbreviations:</strong> Act=Active, BC=Billable Capacity (hrs), B-H=Billable Hours, B%=Billable %, NB-H=Non-Billable Hours, NB%=Non-Billable %, BU=Business Unit | 
            <em>⏰ Generated: {{ timestamp|default('Now') }}</em>
        </small>
    </div>
</div>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
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
            "leftColumns": 2
        },
        "columnDefs": [
            { "orderable": true, "targets": [0, 1, 2, 3] },
            { "orderable": false, "targets": "_all" }
        ]
    });
    
    $('#globalSearch').on('keyup', function() {
        table.search(this.value).draw();
    });
    
    $('#startMonth, #endMonth').on('change', function() {
        var startMonth = $('#startMonth').val();
        var endMonth = $('#endMonth').val();
        window.location.href = '/executive-utilization-dashboard?start_month=' + startMonth + '&end_month=' + endMonth;
    });
});

function exportToExcel() {
    var startMonth = $('#startMonth').val();
    var endMonth = $('#endMonth').val();
    var exportUrl = '/executive-utilization-dashboard/export?start_month=' + startMonth + '&end_month=' + endMonth;
    window.location.href = exportUrl;
}

function emailReport() {
    // Get current user email (you'll need to pass this from Flask)
    var userEmail = '{{ current_user.email }}';  // Add this to your template
    
    if (confirm('Send report to ' + userEmail + '?')) {
        var startMonth = $('#startMonth').val();
        var endMonth = $('#endMonth').val();
        
        // Create a form and submit it
        var form = $('<form method="post" action="/executive-utilization-dashboard/email">');
        form.append('<input type="hidden" name="recipient_email" value="' + userEmail + '">');
        form.append('<input type="hidden" name="start_month" value="' + startMonth + '">');
        form.append('<input type="hidden" name="end_month" value="' + endMonth + '">');
        $('body').append(form);
        form.submit();
    }
}
</script>
</body>
</html>"""