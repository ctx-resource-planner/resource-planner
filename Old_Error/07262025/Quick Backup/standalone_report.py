#!/usr/bin/env python3
"""
Standalone Utilization Report - Completely Independent Flask App
Run this separately to bypass all caching/routing issues
"""

from flask import Flask, render_template_string
import pandas as pd
from sqlalchemy import create_engine, text

app = Flask(__name__)

# HTML Template embedded in Python (no external template files)
REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Executive Utilization Report</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        .service-split {
            display: inline-block;
            padding: 1px 4px;
            border-radius: 3px;
            color: white;
            margin-right: 3px;
            font-weight: bold;
            font-size: 0.75em;
        }
        th, td { 
            white-space: nowrap; 
            text-align: center; 
            padding: 8px 4px !important;
            font-size: 0.85em;
        }
        .employee-name { 
            text-align: left !important; 
            font-weight: bold; 
            min-width: 120px;
        }
        .table { margin-bottom: 0; }
        .legend { font-size: 0.8em; max-height: 60px; overflow: hidden; }
    </style>
</head>
<body>
<div class="container-fluid mt-3">
    <h3 class="mb-2">🎯 Executive Utilization Dashboard</h3>
    
    <!-- Compact Legend -->
    <div class="legend mb-2 p-2" style="background-color: #f8f9fa; border-radius: 5px;">
        <b>Service Lines:</b>
        {% for sl, color in legend.items() %}
            <span style="background:{{ color }}; padding: 1px 4px; border-radius: 2px; color: white; font-size: 0.7em; margin-right: 3px;">{{ sl }}</span>
        {% endfor %}
    </div>

    <!-- Clean Table -->
    <div class="table-responsive">
        <table class="table table-bordered table-striped table-sm">
            <thead class="table-dark">
                <tr>
                    <th class="employee-name">Employee</th>
                    {% for month in months %}
                    <th>{{ month }}<br><small>Billable</small></th>
                    <th>{{ month }}<br><small>Non-Bill</small></th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
            {% for row in rows %}
                <tr>
                    <td class="employee-name">{{ row.name }}</td>
                    {% for month in months %}
                    {% set month_data = row.months.get(month, {}) %}
                    <td>
                        {% if month_data.get('splits', []) and month_data.splits|length > 1 %}
                            {% for split in month_data.splits %}
                                <span class="service-split" style="background-color: {{ split.color }}">
                                    {{ "%.0f"|format(split.billable) }}({{ split.service_line }})
                                </span>
                            {% endfor %}
                            <br><small><b>{{ "%.0f"|format(month_data.get('billable_hours', 0)) }}</b></small>
                        {% else %}
                            <b>{{ "%.0f"|format(month_data.get('billable_hours', 0)) }}</b>
                        {% endif %}
                    </td>
                    <td><b>{{ "%.0f"|format(month_data.get('nonbillable_hours', 0)) }}</b></td>
                    {% endfor %}
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="mt-2">
        <small><b>Total Employees:</b> {{ rows|length }} | <em>Generated: {{ timestamp }}</em></small>
    </div>
</div>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
</body>
</html>
"""

@app.route('/')
def executive_report():
    """Standalone Executive Utilization Report"""
    try:
         # Database connection - UPDATE THESE CREDENTIALS
        # Replace with your actual database connection string
        ##DATABASE_URL = "postgres:W00dward20$$@localhost:5432/resource_planner_dev"
        DATABASE_URL = "postgresql://postgres:W00dward20$$@localhost:5432/resource_planner_dev"
        engine = create_engine(DATABASE_URL)
        
        # Direct SQL query - JOIN with projects table to get service_line
        sql_query = """
        SELECT 
            tu.username,
            CONCAT(tu.first_name, ' ', tu.last_name) as employee_name,
            tu.local_date,
            tu.hours,
            tu.is_billable,
            tu.project_name,
            p.service_line
        FROM timesheet_uploads tu
        LEFT JOIN projects p ON tu.project_name = p.project_name
        ORDER BY tu.username, tu.local_date
        """
        
        df = pd.read_sql(sql_query, engine)
        
        if df.empty:
            return "<h1>No Data Found</h1><p>Check your database connection and table names.</p>"
        
        # Data processing
        df['local_date'] = pd.to_datetime(df['local_date'])
        df['month_name'] = df['local_date'].dt.strftime('%b-%Y')
        
        # Fill missing data
        df['employee_name'] = df['employee_name'].fillna(df['username'])
        df['service_line'] = df['service_line'].fillna('Unknown')
        
        # Get months sorted chronologically
        months = sorted(df['month_name'].unique(), key=lambda x: pd.to_datetime(x, format='%b-%Y'))
        
        # Service line colors for splits (using actual service_line from projects table)
        service_lines = df['service_line'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Group by employee
        employee_groups = df.groupby(['username', 'employee_name'])
        
        rows = []
        for (username, emp_name), emp_df in employee_groups:
            
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
                    
                    monthly_data[month] = {
                        'billable_hours': total_billable,
                        'nonbillable_hours': total_nonbillable,
                        'total_hours': total_hours,
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
                'name': emp_name,
                'months': monthly_data
            })
        
        return render_template_string(REPORT_TEMPLATE,
                                    rows=rows,
                                    months=months,
                                    legend=service_line_colors,
                                    timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p><p>Database connected successfully, but there's an issue with the query or data processing.</p>"

if __name__ == '__main__':
    print("🚀 Starting Standalone Executive Report Server...")
    print("📊 Access your report at: http://127.0.0.1:8888")
    app.run(host='127.0.0.1', port=8888, debug=True)