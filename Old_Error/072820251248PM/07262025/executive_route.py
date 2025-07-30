from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, render_template_string
from flask_login import login_required, current_user
from app import db
from models import TimesheetUpload, Employee
import pandas as pd
from datetime import datetime

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/executive-utilization-dashboard')
@login_required
def executive_utilization_dashboard():
    """Executive Utilization Dashboard using Clean Database View"""
    print("🚀 EXECUTIVE ROUTE CALLED - USING CLEAN DATABASE VIEW")
    
    try:
        import pandas as pd
        from datetime import datetime
        from app import db
        
        # Simple query using the clean view - no more complex JOINs!
        sql_query = "SELECT * FROM dashboard_utilization_data ORDER BY username, local_date"
        df = pd.read_sql(sql_query, db.engine)
        print(f"📊 Query returned {len(df)} rows")

        if df.empty:
            return render_template_string(EXECUTIVE_TEMPLATE, 
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
        df['service_line'] = df['service_line'].fillna('Unknown')
        df['employee_service_line'] = df['employee_service_line'].fillna('Unknown')
        df['project_name'] = df['project_name'].fillna('Unknown')
        
        # Get months and colors
        months = sorted(df['month_name'].unique())
        service_lines = df['service_line'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Group by employee
        employee_groups = df.groupby(['username', 'employee_name', 'employee_service_line', 'doj', 'doe', 'reporting_manager', 'designation', 'location'])
        print(f"📊 Processing {len(employee_groups)} employees")
        
        rows = []
        for (username, emp_name, emp_service_line, doj, doe, mgr, designation, location), emp_df in employee_groups:
            print(f"📊 Processing: {emp_name}")
            
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                if not month_df.empty:
                    # Create splits by project AND service line
                    billable_df = month_df[month_df['is_billable']]
                    project_service_splits = billable_df.groupby(['project_name', 'service_line'])['hours'].sum().reset_index()
                    
                    print(f"📊 {emp_name} in {month}: {len(project_service_splits)} splits found")
                    
                    splits = []
                    for _, row in project_service_splits.iterrows():
                        if row['hours'] > 0:
                            splits.append({
                                'service_line': row['service_line'],
                                'project_name': row['project_name'],
                                'hours': row['hours'],
                                'color': service_line_colors.get(row['service_line'], '#999999')
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
                'service_line': emp_service_line,
                'doj': doj.strftime('%Y-%m-%d') if isinstance(doj, datetime) else str(doj),
                'doe': doe.strftime('%Y-%m-%d') if isinstance(doe, datetime) else str(doe),
                'reporting_manager': mgr,
                'designation': designation,
                'location': location,
                'months': monthly_data
            })
        
        # Filter options
        filter_service_lines = sorted(df['service_line'].unique())
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

# Template with navigation button
EXECUTIVE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Executive Utilization Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.11.5/css/dataTables.bootstrap5.min.css" rel="stylesheet">
</head>
<body>
    <div class="container-fluid">
        <div class="mb-3">
            <a href="{{ url_for('reports.reports_list') }}" class="btn btn-secondary">
                <i class="fas fa-arrow-left"></i> Back to Reports
            </a>
        </div>
        
        <h1><i class="fas fa-chart-line"></i> Executive Utilization Dashboard</h1>
        <p>Employee utilization tracking with service line analysis</p>
        
        <!-- Stats Cards -->
        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card bg-primary text-white">
                    <div class="card-body">
                        <h5>Active Projects</h5>
                        <h2>{{ rows|length }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card bg-success text-white">
                    <div class="card-body">
                        <h5>Active Resources</h5>
                        <h2>{{ rows|length }}</h2>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card bg-info text-white">
                    <div class="card-body">
                        <h5>Total Employees</h5>
                        <h2>{{ rows|length }}</h2>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Legend -->
        <div class="mb-3">
            <strong>Legend:</strong>
            <span class="badge bg-secondary">BU: Business Unit</span>
            <span class="badge bg-secondary">B-H: Billable Hours</span>
            <span class="badge bg-secondary">BH%: Billable Percentage</span>
            <span class="badge bg-secondary">NB-H: Non-Billable Hours</span>
            <span class="badge bg-secondary">NB-H(%): Non-Billable Percentage</span>
        </div>
        
        <!-- Main Table -->
        <div class="table-responsive">
            <table id="utilizationTable" class="table table-striped table-bordered">
                <thead class="table-dark">
                    <tr>
                        <th rowspan="2">Employee</th>
                        <th rowspan="2">BU</th>
                        <th rowspan="2">Manager</th>
                        <th rowspan="2">Status</th>
                        {% for month in months %}
                        <th colspan="6">{{ month }}</th>
                        {% endfor %}
                    </tr>
                    <tr>
                        {% for month in months %}
                        <th>B-H</th>
                        <th>BH%</th>
                        <th>NB-H</th>
                        <th>NB-H(%)</th>
                        <th>Total</th>
                        <th>Active</th>
                        {% endfor %}
                    </tr>
                </thead>
                <tbody>
                    {% for row in rows %}
                    <tr>
                        <td>{{ row.name }}</td>
                        <td>{{ row.service_line }}</td>
                        <td>{{ row.reporting_manager }}</td>
                        <td>
                            {% if row.doe %}
                            <span class="badge bg-secondary">Inactive</span>
                            {% else %}
                            <span class="badge bg-success">Active</span>
                            {% endif %}
                        </td>
                        {% for month in months %}
                        {% set month_data = row.months.get(month, {}) %}
                        <td>
                            {% if month_data.splits %}
                                {% for split in month_data.splits %}
                                <div style="background-color: {{ split.color }}; color: white; padding: 2px 4px; margin: 1px; border-radius: 3px; font-size: 11px;">
                                    {{ split.service_line }}: {{ split.hours }}h
                                </div>
                                {% endfor %}
                            {% else %}
                                {{ month_data.billable_hours|default(0) }}
                            {% endif %}
                        </td>
                        <td>
                            {% if month_data.billable_capacity and month_data.billable_capacity > 0 %}
                            {{ "%.1f"|format((month_data.billable_hours|default(0) / month_data.billable_capacity) * 100) }}%
                            {% else %}
                            0.0%
                            {% endif %}
                        </td>
                        <td>{{ month_data.nonbillable_hours|default(0) }}</td>
                        <td>
                            {% if month_data.total_hours and month_data.total_hours > 0 %}
                            {{ "%.1f"|format((month_data.nonbillable_hours|default(0) / month_data.total_hours) * 100) }}%
                            {% else %}
                            0.0%
                            {% endif %}
                        </td>
                        <td>{{ month_data.total_hours|default(0) }}</td>
                        <td>
                            {% if month_data.total_hours and month_data.total_hours > 0 %}
                            <i class="fas fa-circle text-success"></i>
                            {% else %}
                            <i class="fas fa-circle text-muted"></i>
                            {% endif %}
                        </td>
                        {% endfor %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="mt-3">
            <a href="{{ url_for('reports.reports_list') }}" class="btn btn-secondary">Back to Reports</a>
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
                "leftColumns": 2  // CHANGED: 2 columns (Name + BU) instead of 4
            },
            "columnDefs": [
                { "orderable": true, "targets": [0, 1, 2, 3] },
                { "orderable": false, "targets": "_all" }
            ]
        });
        
        // Single search functionality
        $('#globalSearch').on('keyup', function() {
            table.search(this.value).draw();
        });
        
        // Dynamic date filtering - FIXED: Use correct route path
        $('#startMonth, #endMonth').on('change', function() {
            var startMonth = $('#startMonth').val();
            var endMonth = $('#endMonth').val();
            // CHANGED: Use the correct route path for integrated version
            window.location.href = '/reports/executive-utilization-dashboard?start_month=' + startMonth + '&end_month=' + endMonth;
        });
    });

    function exportToExcel() {
        var startMonth = $('#startMonth').val();
        var endMonth = $('#endMonth').val();
        // TODO: Implement Excel export for integrated version
        alert('Excel export - to be implemented\nRange: ' + startMonth + ' to ' + endMonth);
    }

    function emailReport() {
        var email = prompt("Enter email address:");
        if (email) {
            var startMonth = $('#startMonth').val();
            var endMonth = $('#endMonth').val();
            // TODO: Implement email report for integrated version  
            alert('Email report - to be implemented\nEmail: ' + email + '\nRange: ' + startMonth + ' to ' + endMonth);
        }
    }
    </script>
</body>
</html>
"""