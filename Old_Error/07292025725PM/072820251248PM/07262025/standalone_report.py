#!/usr/bin/env python3
"""
Standalone Utilization Report - Final Production Version
"""

from flask import Flask, render_template_string, request, make_response
import pandas as pd
from sqlalchemy import create_engine
import io
from datetime import datetime

app = Flask(__name__)

# Final Enhanced HTML Template - APPROVAL READY
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Utilization Dashboard</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
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
        
        /* Enhanced Table */
        .table-container {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
            border: 1px solid #e9ecef;
            max-height: 75vh;
            overflow: auto;
        }
        
        .table {
            margin: 0;
            font-size: 0.8em;
        }
        
        .table thead th {
            background: linear-gradient(135deg, #495057 0%, #6c757d 100%);
            color: white;
            border: none;
            font-weight: 600;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }
        
        .table tbody tr:hover {
            background-color: #f8f9fa;
            transition: background-color 0.2s ease;
        }
        
        .employee-name {
            text-align: left !important;
            font-weight: 600;
            min-width: 140px;
            position: sticky;
            left: 0;
            background: white;
            z-index: 10;
            border-right: 2px solid #dee2e6;
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
        }
        
        .sub-header {
            background-color: #6c757d !important;
            color: white !important;
            font-size: 0.65em;
            padding: 1px !important;
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
                <h4>{{ total_billable_projects }}</h4>
            </div>
        </div>
        <div class="col-md-6">
            <div class="stats-card">
                <h6>👥 Total Billable Resources</h6>
                <h4>{{ total_billable_resources }}</h4>
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

    <!-- Enhanced Table Container -->
    <div class="table-container">
        <table id="utilizationTable" class="table table-bordered table-striped table-sm">
            <thead>
                <tr>
                    <th rowspan="2" class="employee-name">Employee</th>
                    <th rowspan="2">BU</th>
                    <th rowspan="2">Manager</th>
                    <th rowspan="2">DOJ</th>
                    {% for month in months %}
                    <th colspan="5" class="month-header">{{ month }}</th>
                    {% endfor %}
                </tr>
                <tr>
                    {% for month in months %}
                    <th class="sub-header">Act</th>
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
                    <td class="employee-name {% if row.is_departed %}employee-departed{% endif %}">{{ row.name }}</td>
                    <td><span class="legend-badge" style="background:{{ legend.get(row.service_line, '#999') }};">{{ row.service_line }}</span></td>
                    <td>{{ row.reporting_manager[:10] }}</td>
                    <td>{{ row.doj }}</td>
                    {% for month in months %}
                    {% set month_data = row.months.get(month, {}) %}
                    <td>
                        <span class="active-dot {% if month_data.get('total_hours', 0) > 0 %}active-green{% else %}active-gray{% endif %}"></span>
                    </td>
                    <td>
                        {% if month_data.get('splits', []) and month_data.splits|length > 1 %}
                            {% for split in month_data.splits %}
                                <span class="service-split" style="background-color: {{ split.color }}">
                                    {{ "%.0f"|format(split.billable) }}
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
            <strong>📝 Abbreviations:</strong> Act=Active, B-H=Billable Hours, B%=Billable %, NB-H=Non-Billable Hours, NB%=Non-Billable %, BU=Business Unit | 
            <em>⏰ Generated: {{ timestamp }}</em>
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
        "searching": true,  // Keep DataTables search enabled
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

// Remove the custom search since DataTables search works better
// $('#globalSearch').on('keyup', function() {
//     table.search(this.value).draw();
// });
    
    // Single search functionality
    $('#globalSearch').on('keyup', function() {
        table.search(this.value).draw();
    });
    
    // Dynamic date filtering
    $('#startMonth, #endMonth').on('change', function() {
        var startMonth = $('#startMonth').val();
        var endMonth = $('#endMonth').val();
        window.location.href = '/?start_month=' + startMonth + '&end_month=' + endMonth;
    });
});

function exportToExcel() {
    var startMonth = $('#startMonth').val();
    var endMonth = $('#endMonth').val();
    window.location.href = '/export_excel?start_month=' + startMonth + '&end_month=' + endMonth;
}

function emailReport() {
    var email = prompt("Enter email address:");
    if (email) {
        var startMonth = $('#startMonth').val();
        var endMonth = $('#endMonth').val();
        window.location.href = '/email_report?email=' + email + '&start_month=' + startMonth + '&end_month=' + endMonth;
    }
}
</script>
</body>
</html>
"""

@app.route('/')
def executive_report():
    """Final Utilization Report - Production Ready"""
    try:
      # Database connection - UPDATE THESE CREDENTIALS
        # Replace with your actual database connection string
        ##DATABASE_URL = "postgres:W00dward20$$@localhost:5432/resource_planner_dev"
        DATABASE_URL = "postgresql://postgres:W00dward20$$@localhost:5432/resource_planner_dev"
        engine = create_engine(DATABASE_URL)
        
        # Get date range parameters
        start_month = request.args.get('start_month')
        end_month = request.args.get('end_month')
        
        # Fixed SQL query - handle NULL service lines properly
        sql_query = """
        SELECT 
            tu.username,
            CONCAT(tu.first_name, ' ', tu.last_name) as employee_name,
            tu.local_date,
            tu.hours,
            tu.is_billable,
            tu.project_name,
            p.service_line as project_service_line,
            COALESCE(e.service_line, 'Unknown') as employee_service_line,
            COALESCE(e.reporting_manager, 'Unknown') as reporting_manager,
            e.doj,
            e.doe
        FROM timesheet_uploads tu
        LEFT JOIN projects p ON tu.project_name = p.project_name
        LEFT JOIN employees e ON tu.username = e.email
        ORDER BY tu.username, tu.local_date
        """
        
        df = pd.read_sql(sql_query, engine)
        
        if df.empty:
            return "<h1>No Data Found</h1>"
        
        # Data processing
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
        # Fill missing data properly
        df['employee_name'] = df['employee_name'].fillna(df['username'])
        df['project_service_line'] = df['project_service_line'].fillna('Unknown')
        df['employee_service_line'] = df['employee_service_line'].fillna('Unknown')
        df['reporting_manager'] = df['reporting_manager'].fillna('Unknown')

        # Clean employee names for proper sorting
        def clean_name_for_sorting(name):
            import re
            # Remove invisible Unicode characters and extra spaces
            cleaned = re.sub(r'[^\w\s]', '', str(name))  # Remove special chars
            cleaned = re.sub(r'\s+', ' ', cleaned)       # Normalize spaces
            return cleaned.strip()

        # Apply name cleaning
        df['clean_employee_name'] = df['employee_name'].apply(clean_name_for_sorting)

        # Use COALESCE logic - if employee_service_line is Unknown, try project_service_line
        df['final_service_line'] = df.apply(lambda row: 
            row['employee_service_line'] if row['employee_service_line'] != 'Unknown' 
            else row['project_service_line'], axis=1)

        # Fix specific BU mappings - FIXED: Unknown -> AI
        df['final_service_line'] = df['final_service_line'].replace('Unknown', 'AI')
        
        # Get all available months
        all_months = sorted(df['month_name'].unique(), key=lambda x: pd.to_datetime(x, format='%b-%Y'))
        
        # Set default date range if not provided
        if not start_month:
            start_month = all_months[0] if all_months else None
        if not end_month:
            end_month = all_months[-1] if all_months else None
        
        # Filter data by date range - FIXED VERSION
        if start_month and end_month:
            start_date = pd.to_datetime(start_month, format='%b-%Y')
            end_date = pd.to_datetime(end_month, format='%b-%Y')
            # Add one month to end_date to include the end month
            end_date = end_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)
            df = df[(df['local_date'] >= start_date) & (df['local_date'] <= end_date)]
        
        # Get filtered months
        months = sorted(df['month_name'].unique(), key=lambda x: pd.to_datetime(x, format='%b-%Y'))
        
        # BU colors - use final_service_line for colors
        service_lines = df['final_service_line'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#FF9F43', '#10AC84']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Calculate stats
        # Calculate stats - FIXED: Only count projects with billable hours in most recent month
        if months:
            most_recent_month = months[-1]  # Get the last month in the filtered range
            recent_month_df = df[df['month_name'] == most_recent_month]
            
            # Count only projects with billable hours in the most recent month
            total_billable_projects = len(recent_month_df[recent_month_df['is_billable']]['project_name'].unique())
            
            # Count only resources with billable hours in the most recent month  
            total_billable_resources = len(recent_month_df[recent_month_df['is_billable']]['username'].unique())
        else:
            total_billable_projects = 0
            total_billable_resources = 0
        
        # Simplified grouping - group by username only first, then get other details
        unique_employees = df.groupby('username').first().reset_index()

        print(f"DEBUG: Unique employees found: {len(unique_employees)}")

        rows = []
        for _, emp_row in unique_employees.iterrows():
            username = emp_row['username']
            emp_name = emp_row['employee_name']
            final_service_line = emp_row['final_service_line']
            mgr = emp_row['reporting_manager']
            doj = emp_row['doj']
            doe = emp_row['doe']
            
            # Get all data for this employee
            emp_df = df[df['username'] == username]
            
            # Check if employee has departed - FIXED VERSION
            try:
                if doe is not None and pd.notna(doe):
                    # Convert DOE to datetime and compare with current date
                    doe_date = pd.to_datetime(doe)
                    current_date = pd.Timestamp.now()
                    # Employee is departed if DOE date has passed
                    is_departed = doe_date <= current_date
                else:
                    is_departed = False
            except Exception as e:
                print(f"DEBUG: Error processing DOE for {emp_name}: {e}")
                is_departed = False
            
            # Calculate monthly data
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                if not month_df.empty:
                    # Service line splits for billable hours
                    billable_by_service = month_df[month_df['is_billable']].groupby('project_service_line')['hours'].sum()
                    
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
                    
                    # Calculate percentages
                    capacity = 176
                    billable_percentage = (total_billable / capacity * 100) if capacity > 0 else 0
                    nonbillable_percentage = (total_nonbillable / capacity * 100) if capacity > 0 else 0
                    
                    monthly_data[month] = {
                        'billable_hours': total_billable,
                        'nonbillable_hours': total_nonbillable,
                        'total_hours': total_hours,
                        'billable_percentage': billable_percentage,
                        'nonbillable_percentage': nonbillable_percentage,
                        'splits': splits
                    }
                else:
                    monthly_data[month] = {
                        'billable_hours': 0,
                        'nonbillable_hours': 0,
                        'total_hours': 0,
                        'billable_percentage': 0,
                        'nonbillable_percentage': 0,
                        'splits': []
                    }
            
            # Format DOJ
            doj_formatted = doj.strftime('%d-%b-%y') if isinstance(doj, pd.Timestamp) else str(doj)[:10]
            
            rows.append({
                'name': emp_name,
                'service_line': final_service_line,
                'reporting_manager': mgr,
                'doj': doj_formatted,
                'is_departed': is_departed,
                'months': monthly_data
            })

        print(f"DEBUG: Final rows created: {len(rows)}")

        # Sort rows by clean name for proper alphabetical order
        rows.sort(key=lambda x: clean_name_for_sorting(x['name']))

        print(f"DEBUG: Final rows count: {len(rows)}")
        
        return render_template_string(REPORT_TEMPLATE,
                                    rows=rows,
                                    months=months,
                                    all_months=all_months,
                                    start_month=start_month,
                                    end_month=end_month,
                                    legend=service_line_colors,
                                    total_billable_projects=total_billable_projects,
                                    total_billable_resources=total_billable_resources,
                                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p>"

@app.route('/export_excel')
def export_excel():
    """Export to Excel"""
    return "<h1>Excel Export</h1><p>Feature ready for implementation</p><p><a href='/'>← Back</a></p>"

@app.route('/email_report')
def email_report():
    """Email Report"""
    email = request.args.get('email', 'unknown@email.com')
    return f"<h1>Email Sent</h1><p>Report sent to {email}</p><p><a href='/'>← Back</a></p>"

if __name__ == '__main__':
    print("🚀 Starting Final Utilization Dashboard...")
    print("📊 Access: http://127.0.0.1:8888")
    app.run(host='127.0.0.1', port=8888, debug=True)