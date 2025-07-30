from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, render_template_string
from flask_login import login_required, current_user
import pandas as pd
from datetime import datetime, timedelta
import calendar

reports_bp = Blueprint('reports', __name__)

# --- Main Routes ---
@reports_bp.route('/test')
@login_required
def test():
    """Simple test route to verify blueprint and authentication"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return "❌ Access denied. Admin access required."
    return "✅ Reports blueprint is working! User: " + str(current_user.username)

@reports_bp.route('/debug_test_123')
@login_required
def debug_test_123():
    return "🚀 NEW CODE IS WORKING! This proves the file is being used."
    
    
@reports_bp.route('/utilization')
@login_required
def utilization():
    """Executive Utilization Dashboard - Main Feature"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))
    
    try:
        from app import db
        
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
            return render_template_string(UTILIZATION_TEMPLATE, 
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
        
        return render_template_string(UTILIZATION_TEMPLATE, 
                                    employees=employees_data, 
                                    months=month_strings,
                                    service_lines=service_line_colors,
                                    stats=stats)
        
    except Exception as e:
        flash(f"Error loading utilization data: {str(e)}", "danger")
        return render_template_string(UTILIZATION_TEMPLATE, 
                                    employees=[], months=[], 
                                    service_lines={}, stats={})

# --- All Missing Routes (Simple Placeholders) ---
@reports_bp.route('/reports_list')
@login_required  
def reports_list():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    
    # Instead of returning simple HTML, render the actual template
    return render_template('reports_list.html')
    

@reports_bp.route('/monthwise_utilization_report')
@login_required
def monthwise_utilization_report():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return render_template('monthwise_utilization_report.html')

@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return render_template('allocation_matrix.html')

@reports_bp.route('/simple_utilization_report')
@login_required
def simple_utilization_report():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return render_template('simple_utilization_report.html')

@reports_bp.route('/utilization_report')
@login_required
def utilization_report():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return render_template('utilization_report.html')

@reports_bp.route('/projects_summary')
@login_required
def projects_summary():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return '<h1>📋 Projects Summary</h1><p><a href="/reports/utilization">Go to Utilization Dashboard</a></p>'

@reports_bp.route('/skills_proficiency')
@login_required
def skills_proficiency():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return '<h1>🎯 Skills Proficiency</h1><p><a href="/reports/utilization">Go to Utilization Dashboard</a></p>'

@reports_bp.route('/projects_billable_allocation')
@login_required
def projects_billable_allocation():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return '<h1>💰 Billable Allocation</h1><p><a href="/reports/utilization">Go to Utilization Dashboard</a></p>'

@reports_bp.route('/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        return redirect(url_for('main.index'))
    return '<h1>📤 Upload Utilization</h1><p><a href="/reports/utilization">Go to Utilization Dashboard</a></p>'

# --- Redirect Routes ---
@reports_bp.route('/resource_utilization_dashboard')
@login_required
def resource_utilization_dashboard():
    return redirect(url_for('reports.utilization'))

@reports_bp.route('/resource_utilization_report')
@login_required
def resource_utilization_report():
    return redirect(url_for('reports.utilization'))

@reports_bp.route('/working_utilization_report')
@login_required
def working_utilization_report():
    return redirect(url_for('reports.utilization'))



# --- Main Template ---
UTILIZATION_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Utilization Dashboard</title>
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
        <div class="row mb-4">
            <div class="col-md-8">
                <h1 class="mb-0">📊 Utilization Dashboard</h1>
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

    