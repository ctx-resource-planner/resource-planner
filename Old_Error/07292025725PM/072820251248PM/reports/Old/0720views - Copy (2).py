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

# --- Reports List Page ---
@reports_bp.route('/reports_list')
@login_required  
def reports_list():
    """Available Reports List - Working Implementation"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))
    
    reports_data = {
        'utilization': {
            'title': 'Executive Utilization Dashboard',
            'description': 'Comprehensive employee utilization tracking with service line splits, billable/non-billable hours, and monthly breakdowns.',
            'url': url_for('reports.utilization'),
            'icon': '📊',
            'status': 'active'
        },
        'allocation_matrix': {
            'title': 'Employee Allocation Matrix',
            'description': 'Matrix view of employee allocations across projects and time periods.',
            'url': url_for('reports.allocation_matrix'),
            'icon': '🔲',
            'status': 'development'
        },
        'projects_summary': {
            'title': 'Projects Summary',
            'description': 'Overview of all projects with key metrics and status information.',
            'url': url_for('reports.projects_summary'),
            'icon': '📋',
            'status': 'development'
        },
        'skills_proficiency': {
            'title': 'Skills Proficiency Analysis',
            'description': 'Employee skills assessment and proficiency tracking.',
            'url': url_for('reports.skills_proficiency'),
            'icon': '🎯',
            'status': 'development'
        },
        'billable_allocation': {
            'title': 'Billable Hours Allocation',
            'description': 'Analysis of billable hours distribution across projects and employees.',
            'url': url_for('reports.projects_billable_allocation'),
            'icon': '💰',
            'status': 'development'
        }
    }
    
    return render_template_string(REPORTS_LIST_TEMPLATE, reports=reports_data)

# --- Projects Summary Report ---
@reports_bp.route('/projects_summary')
@login_required
def projects_summary():
    """Projects Summary Report - Working Implementation"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))
    
    try:
        from app import db
        
        # Get project summary data
        sql_query = """
        SELECT 
            p.project_name,
            p.service_line,
            p.client_name,
            COUNT(DISTINCT tu.username) as total_resources,
            SUM(CASE WHEN tu.is_billable = true THEN tu.hours ELSE 0 END) as billable_hours,
            SUM(CASE WHEN tu.is_billable = false THEN tu.hours ELSE 0 END) as non_billable_hours,
            SUM(tu.hours) as total_hours,
            MIN(tu.local_date) as start_date,
            MAX(tu.local_date) as end_date
        FROM projects p
        LEFT JOIN timesheet_uploads tu ON p.project_name = tu.project_name
        GROUP BY p.project_name, p.service_line, p.client_name
        ORDER BY total_hours DESC
        """
        
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            projects_data = []
        else:
            df['billable_percentage'] = (df['billable_hours'] / df['total_hours'] * 100).round(1)
            projects_data = df.to_dict(orient='records')
        
        return render_template_string(PROJECTS_SUMMARY_TEMPLATE, projects=projects_data)
        
    except Exception as e:
        flash(f"Error loading projects summary: {str(e)}", "danger")
        return render_template_string(PROJECTS_SUMMARY_TEMPLATE, projects=[])

# --- Skills Proficiency Report ---
@reports_bp.route('/skills_proficiency')
@login_required
def skills_proficiency():
    """Skills Proficiency Report - Working Implementation"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))
    
    try:
        from app import db
        
        # Get employee skills data
        sql_query = """
        SELECT 
            e.name as employee_name,
            e.service_line,
            e.designation,
            es.skill_name,
            es.proficiency_level,
            es.years_experience,
            es.last_updated
        FROM employees e
        LEFT JOIN employee_skills es ON e.id = es.employee_id
        ORDER BY e.name, es.skill_name
        """
        
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            skills_data = []
        else:
            # Group by employee
            skills_data = []
            for employee in df['employee_name'].unique():
                emp_data = df[df['employee_name'] == employee].iloc[0]
                emp_skills = df[df['employee_name'] == employee][['skill_name', 'proficiency_level', 'years_experience']].to_dict(orient='records')
                
                skills_data.append({
                    'employee_name': employee,
                    'service_line': emp_data['service_line'],
                    'designation': emp_data['designation'],
                    'skills': emp_skills
                })
        
        return render_template_string(SKILLS_PROFICIENCY_TEMPLATE, employees=skills_data)
        
    except Exception as e:
        flash(f"Error loading skills data: {str(e)}", "danger")
        return render_template_string(SKILLS_PROFICIENCY_TEMPLATE, employees=[])

# --- Allocation Matrix Report ---
@reports_bp.route('/allocation_matrix')
@login_required
def allocation_matrix():
    """Employee Allocation Matrix Report - Working Implementation"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))
    
    try:
        from app import db
        
        # Get allocation matrix data
        sql_query = """
        SELECT 
            CONCAT(tu.first_name, ' ', tu.last_name) as employee_name,
            tu.project_name,
            DATE_TRUNC('month', tu.local_date) as month_year,
            SUM(tu.hours) as total_hours,
            SUM(CASE WHEN tu.is_billable = true THEN tu.hours ELSE 0 END) as billable_hours
        FROM timesheet_uploads tu
        WHERE tu.local_date >= CURRENT_DATE - INTERVAL '6 months'
        GROUP BY employee_name, tu.project_name, month_year
        ORDER BY employee_name, month_year, total_hours DESC
        """
        
        df = pd.read_sql(sql_query, db.engine)
        
        if df.empty:
            allocation_data = []
        else:
            df['month_year'] = pd.to_datetime(df['month_year']).dt.strftime('%b-%Y')
            df['allocation_percentage'] = (df['billable_hours'] / df['total_hours'] * 100).round(1)
            allocation_data = df.to_dict(orient='records')
        
        return render_template_string(ALLOCATION_MATRIX_TEMPLATE, allocations=allocation_data)
        
    except Exception as e:
        flash(f"Error loading allocation matrix: {str(e)}", "danger")
        return render_template_string(ALLOCATION_MATRIX_TEMPLATE, allocations=[])

# --- Upload Utilization Report ---
@reports_bp.route('/upload_utilization', methods=['GET', 'POST'])
@login_required
def upload_utilization():
    """Upload Utilization Report - Working Implementation"""
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash("Access denied. This page is only available to administrators.", "danger")
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Handle file upload (placeholder for now)
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and file.filename.endswith(('.xlsx', '.xls', '.csv')):
            flash(f'File "{file.filename}" uploaded successfully! Processing functionality will be implemented soon.', 'success')
        else:
            flash('Please upload an Excel (.xlsx, .xls) or CSV file', 'error')
        
        return redirect(url_for('reports.upload_utilization'))
    
    return render_template_string(UPLOAD_UTILIZATION_TEMPLATE)

# --- Additional Routes (Redirects to main features) ---
@reports_bp.route('/projects_billable_allocation')
@login_required
def projects_billable_allocation():
    """Projects Billable Allocation Report - Redirect to projects summary"""
    return redirect(url_for('reports.projects_summary'))

@reports_bp.route('/resource_utilization_dashboard')
@login_required
def resource_utilization_dashboard():
    """Resource Utilization Dashboard - Redirect to main dashboard"""
    return redirect(url_for('reports.utilization'))

@reports_bp.route('/resource_utilization_report')
@login_required
def resource_utilization_report():
    """Resource Utilization Report - Redirect to main dashboard"""
    return redirect(url_for('reports.utilization'))

@reports_bp.route('/monthwise_utilization_report')
@login_required
def monthwise_utilization_report():
    """Monthly Utilization Report - Redirect to main dashboard"""
    return redirect(url_for('reports.utilization'))

@reports_bp.route('/working_utilization_report')
@login_required
def working_utilization_report():
    """Working Utilization Report - Redirect to main dashboard"""
    return redirect(url_for('reports.utilization'))

# --- HTML Templates ---
UTILIZATION_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Utilization Dashboard</title>
    <link href="[https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css](https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css)" rel="stylesheet">
    <link href="[https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css](https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css)" rel="stylesheet">
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
            <span class="legend-item"><strong>DOJ:</strong> Date of Joining</span>
            <span class="legend-item"><strong>DOE:</strong> Date of Exit</span>
        </div>

        <div class="table-responsive">
            <table id="utilizationTable" class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Employee</th>
                        <th>BU</th>
                        <th>Manager</th>
                        <th>DOJ</th>
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
                        <td>{{ employee.doj }}</td>
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

    <script src="[https://code.jquery.com/jquery-3.7.0.min.js"></script](https://code.jquery.com/jquery-3.7.0.min.js"></script)>
    <script src="[https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script](https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script)>
    <script src="[https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script](https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script)>
    <script>
        $(document).ready(function() {
            $('#utilizationTable').DataTable({
                "pageLength": 25,
                "scrollX": true,
                "fixedColumns": { "leftColumns": 5 },
                "order": [[ 0, "asc" ]]
            });
        });
    </script>
</body>
</html>
"""

REPORTS_LIST_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Available Reports</title>
    <link href="[https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css](https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css)" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; }
        .container { background: white; border-radius: 15px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .report-card { border: 1px solid #e9ecef; border-radius: 10px; padding: 20px; margin-bottom: 20px; transition: transform 0.2s; }
        .report-card:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .status-active { color: #28a745; font-weight: bold; }
        .status-development { color: #ffc107; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">📊 Available Reports</h1>
        {% for key, report in reports.items() %}
        <div class="report-card">
            <div class="row align-items-center">
                <div class="col-md-1 text-center">
                    <span style="font-size: 2rem;">{{ report.icon }}</span>
                </div>
                <div class="col-md-8">
                    <h5 class="mb-1">{{ report.title }}</h5>
                    <p class="mb-1 text-muted">{{ report.description }}</p>
                    <small class="status-{{ report.status }}">● {{ report.status.title() }}</small>
                </div>
                <div class="col-md-3 text-end">
                    <a href="{{ report.url }}" class="btn btn-primary">View Report</a>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

PROJECTS_SUMMARY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Projects Summary</title>
    <link href="[https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css](https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css)" rel="stylesheet">
    <link href="[https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css](https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css)" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; }
        .container { background: white; border-radius: 15px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">📋 Projects Summary</h1>
        <div class="table-responsive">
            <table id="projectsTable" class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Project Name</th>
                        <th>Service Line</th>
                        <th>Client</th>
                        <th>Resources</th>
                        <th>Billable Hours</th>
                        <th>Non-Billable Hours</th>
                        <th>Total Hours</th>
                        <th>Billable %</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>
                    {% for project in projects %}
                    <tr>
                        <td>{{ project.project_name or 'N/A' }}</td>
                        <td>{{ project.service_line or 'N/A' }}</td>
                        <td>{{ project.client_name or 'N/A' }}</td>
                        <td>{{ project.total_resources or 0 }}</td>
                        <td>{{ "%.1f"|format(project.billable_hours or 0) }}</td>
                        <td>{{ "%.1f"|format(project.non_billable_hours or 0) }}</td>
                        <td>{{ "%.1f"|format(project.total_hours or 0) }}</td>
                        <td>{{ "%.1f"|format(project.billable_percentage or 0) }}%</td>
                        <td>{{ project.start_date }} to {{ project.end_date }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    <script src="[https://code.jquery.com/jquery-3.7.0.min.js"></script](https://code.jquery.com/jquery-3.7.0.min.js"></script)>
    <script src="[https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script](https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script)>
    <script src="[https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script](https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script)>
    <script>
        $(document).ready(function() {
            $('#projectsTable').DataTable({
                "pageLength": 25,
                "order": [[ 6, "desc" ]]
            });
        });
    </script>
</body>
</html>
"""

SKILLS_PROFICIENCY_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Skills Proficiency</title>
    <link href="[https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css](https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css)" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; }
        .container { background: white; border-radius: 15px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
        .skill-badge { display: inline-block; margin: 2px; padding: 5px 10px; border-radius: 15px; font-size: 0.8rem; }
        .skill-beginner { background: #f8d7da; color: #721c24; }
        .skill-intermediate { background: #fff3cd; color: #856404; }
        .skill-advanced { background: #d1ecf1; color: #0c5460; }
        .skill-expert { background: #d4edda; color: #155724; }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">🎯 Skills Proficiency Analysis</h1>
        {% if employees %}