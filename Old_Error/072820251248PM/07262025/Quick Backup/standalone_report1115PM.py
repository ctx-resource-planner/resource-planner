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
            padding: 2px 6px;
            border-radius: 5px;
            color: #fff;
            margin-right: 2px;
            font-weight: bold;
            font-size: 0.95em;
        }
        th, td { white-space: nowrap; text-align: center; }
        .employee-name { text-align: left !important; font-weight: bold; }
        .legend-box {
            display: inline-block;
            width: 18px;
            height: 18px;
            border-radius: 4px;
            margin-right: 5px;
            vertical-align: middle;
        }
    </style>
</head>
<body>
<div class="container-fluid mt-4">
    <h2 class="mb-4">🎯 Executive Utilization Dashboard</h2>
    
    <!-- Legend -->
    <div class="mb-3 p-3" style="background-color: #f8f9fa; border-radius: 5px;">
        <b>Legend:</b>
        {% for sl, color in legend.items() %}
            <span class="legend-box" style="background:{{ color }}"></span> {{ sl }}
        {% endfor %}
        <br>
        <b>Columns:</b> Act = Active, Cap = Capacity, BHrs = Billable Hours, B% = Billable %, NBHrs = Non-Billable Hours
    </div>

    <!-- Executive Table -->
    <div class="table-responsive">
        <table class="table table-bordered table-striped" style="font-size: 0.9em;">
            <thead class="table-dark">
                <tr>
                    <th>Employee</th>
                    <th>Service Line</th>
                    <th>Designation</th>
                    <th>Manager</th>
                    {% for month in months %}
                    <th>{{ month }} - Billable</th>
                    <th>{{ month }} - Non-Billable</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
            {% for row in rows %}
                <tr>
                    <td class="employee-name">{{ row.name }}</td>
                    <td>{{ row.service_line }}</td>
                    <td>{{ row.designation }}</td>
                    <td>{{ row.reporting_manager }}</td>
                    {% for month in months %}
                    {% set month_data = row.months.get(month, {}) %}
                    <td>
                        {% if month_data.get('splits', []) and month_data.splits|length > 1 %}
                            {% for split in month_data.splits %}
                                <span style="background-color: {{ split.color }}; padding: 1px 4px; border-radius: 2px; color: white; font-size: 0.8em; margin-right: 2px;">
                                    {{ "%.0f"|format(split.billable) }}({{ split.service_line }})
                                </span>
                            {% endfor %}
                            <br><b>{{ "%.0f"|format(month_data.get('billable_hours', 0)) }}</b>
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
    
    <div class="mt-3">
        <p><strong>Total Records:</strong> {{ rows|length }}</p>
        <p><em>Generated: {{ timestamp }}</em></p>
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
        
        # Direct SQL query - bypasses all ORM issues
        # Direct SQL query - bypasses all ORM issues
        sql_query = """
        SELECT *
        FROM timesheet_uploads 
        LIMIT 5
        """

        df = pd.read_sql(sql_query, engine)

        if df.empty:
            return "<h1>No Data Found</h1><p>Check your database connection and table names.</p>"

        # DEBUG: Show what columns and data we have - return immediately for debugging
        return f"""
        <h1>🔍 TIMESHEET_UPLOADS TABLE STRUCTURE</h1>
        <h3>All Available Columns:</h3>
        <p>{list(df.columns)}</p>

        <h3>Sample Data (first 5 rows):</h3>
        <pre style="font-size: 0.8em;">{df.to_string()}</pre>

        <h3>Column Data Types:</h3>
        <pre>{df.dtypes.to_string()}</pre>

        <h3>Looking for project/service line columns...</h3>
        <p>We need to find columns that contain project or service line information for splits.</p>
        """
               
        df = pd.read_sql(sql_query, engine)
        
        if df.empty:
            return "<h1>No Data Found</h1><p>Check your database connection and table names.</p>"
            
            
# DEBUG: Show what columns and data we have - return immediately for debugging
        return f"""
        <h1>🔍 DEBUG INFO</h1>
        <h3>Available Columns:</h3>
        <p>{list(df.columns)}</p>

        <h3>Sample Data (first 10 rows):</h3>
        <pre style="font-size: 0.8em;">{df.head(10).to_string()}</pre>

        <h3>Unique service_lines:</h3>
        <p>{df['service_line'].unique()}</p>

        <h3>Sample employee timesheet entries:</h3>
        <pre style="font-size: 0.8em;">{df[df['username'] == df['username'].iloc[0]].head(5).to_string()}</pre>

        <h3>Do we have project-level data?</h3>
        <p>Looking for columns that might contain project or task information...</p>
        """


            # DEBUG: Show what columns and data we have
        debug_info = f"""
            <h3>🔍 DEBUG INFO:</h3>
            <p><b>Available Columns:</b> {list(df.columns)}</p>
            <p><b>Sample Data (first 10 rows):</b></p>
            <pre>{df.head(10).to_string()}</pre>
            <p><b>Unique service_lines:</b> {df['service_line'].unique()}</p>
            <p><b>Sample employee data:</b></p>
            <pre>{df[df['username'] == df['username'].iloc[0]].head(5).to_string()}</pre>
             <hr>
            """
            
        # Data processing
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
        df['reporting_manager'] = df['reporting_manager'].fillna('Unknown')
        df['designation'] = df['designation'].fillna('Unknown')
        
        # Get months
        months = sorted(df['month_name'].unique())
        
        # Service line colors
        service_lines = df['service_line'].unique()
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        service_line_colors = {sl: colors[i % len(colors)] for i, sl in enumerate(service_lines)}
        
        # Group by employee
        employee_groups = df.groupby(['username', 'employee_name', 'service_line', 'reporting_manager', 'designation'])
        
        rows = []
        for (username, emp_name, service_line, mgr, designation), emp_df in employee_groups:
            monthly_data = {}
            for month in months:
                month_df = emp_df[emp_df['month_name'] == month]
                
                if not month_df.empty:
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
            
            rows.append({
                'name': emp_name,
                'service_line': service_line,
                'reporting_manager': mgr,
                'designation': designation,
                'months': monthly_data
            })
        
        return debug_info + render_template_string(REPORT_TEMPLATE,
                            rows=rows,
                            months=months,
                            legend=service_line_colors,
                            timestamp=pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))
        
    except Exception as e:
        return f"<h1>Error</h1><p>{str(e)}</p><p>Update the DATABASE_URL in the code with your actual database connection.</p>"

if __name__ == '__main__':
    print("🚀 Starting Standalone Executive Report Server...")
    print("📊 Access your report at: http://127.0.0.1:8888")
    app.run(host='127.0.0.1', port=8888, debug=True)
