# 1. Create backup
$backupName = "app_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').py"
Copy-Item -Path "app.py" -Destination $backupName
Write-Host "Backup created: $backupName" -ForegroundColor Green

# 2. Add required imports
$importsToAdd = @(
    "from flask import send_file, make_response, request, current_app",
    "from io import BytesIO",
    "import pandas as pd",
    "from sqlalchemy import text, func",
    "from datetime import datetime",
    "from flask_mail import Message"
)

$currentImports = Get-Content -Path "app.py" -Raw
$newImports = $currentImports
foreach ($import in $importsToAdd) {
    if (-not $currentImports.Contains($import.Split(' ')[-1])) {
        $newImports = $import.Trim() + "`n" + $newImports
    }
}

# 3. Add the report code
$reportCode = @"

# ===================================================
# Projects Report Routes and Functions
# ===================================================
@app.route('/reports/projects')
@login_required
def projects_report():
    try:
        # Get projects with their allocations
        projects = Project.query.options(joinedload(Project.allocations)).all()
        
        # Calculate allocations
        for project in projects:
            total_allocation = sum(
                alloc.billable_allocation_percentage / 100.0
                for alloc in project.allocations
                if alloc.billable_allocation_percentage is not None
            )
            project.actual_allocation_fte = round(total_allocation, 2)

        # Handle Excel export
        if 'export' in request.args:
            return export_projects_to_excel(projects)
            
        # Handle email
        if 'email' in request.args:
            return email_projects_report(projects)
            
        return render_template('projects_report.html', 
                            projects=projects,
                            current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    except Exception as e:
        print(f"Error in projects_report: {str(e)}")
        flash('An error occurred while generating the report.', 'danger')
        return redirect(url_for('projects_list'))

def export_projects_to_excel(projects):
    try:
        data = [{
            'Project Name': p.name,
            'Status': p.status or 'Active',
            'Service Line': p.service_line or 'N/A',
            'Project Type': p.project_type or 'N/A',
            'SOW Start': p.sow_start_date.strftime('%Y-%m-%d') if p.sow_start_date else 'N/A',
            'SOW End': p.sow_end_date.strftime('%Y-%m-%d') if p.sow_end_date else 'N/A',
            'Actual Start': p.actual_start_date.strftime('%Y-%m-%d') if p.actual_start_date else 'N/A',
            'Actual End': p.actual_end_date.strftime('%Y-%m-%d') if p.actual_end_date else 'N/A',
            'PO Amount': float(p.po_amount) if p.po_amount else 0.0,
            'SOW Allocation': float(p.sow_allocation_fte) if p.sow_allocation_fte else 0.0,
            'Actual Allocation': float(getattr(p, 'actual_allocation_fte', 0)) or 0.0
        } for p in projects]

        df = pd.DataFrame(data)
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Projects Report', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Projects Report']
            
            # Format headers
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # Format numbers
            number_format = workbook.add_format({'num_format': '0.00'})
            
            # Apply formats
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)
            
            # Format numeric columns
            for col in ['PO Amount', 'SOW Allocation', 'Actual Allocation']:
                if col in df.columns:
                    col_idx = df.columns.get_loc(col)
                    worksheet.set_column(col_idx, col_idx, 15, number_format)
        
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name=f"projects_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        print(f"Error in export_projects_to_excel: {str(e)}")
        flash('Error generating Excel file.', 'danger')
        return redirect(url_for('projects_report'))

def email_projects_report(projects):
    try:
        # Generate Excel file
        output = BytesIO()
        df = pd.DataFrame([{
            'Project Name': p.name,
            'Status': p.status or 'Active',
            'Service Line': p.service_line or 'N/A',
            'Actual Allocation': float(getattr(p, 'actual_allocation_fte', 0)) or 0.0
        } for p in projects])
        
        df.to_excel(output, index=False)
        output.seek(0)
        
        # Get email configuration
        sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@example.com')
        recipients = [current_user.email]
        
        # Create and send email
        msg = Message(
            "Projects Allocation Report",
            sender=sender,
            recipients=recipients
        )
        msg.body = "Please find attached the projects allocation report."
        
        # Attach Excel file
        msg.attach(
            "projects_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            output.read()
        )
        
        # Send email
        mail = current_app.extensions.get('mail')
        if mail:
            mail.send(msg)
            flash('Report has been sent to your email.', 'success')
        else:
            flash('Email service not configured. Please contact administrator.', 'warning')
        
    except Exception as e:
        print(f"Error in email_projects_report: {str(e)}")
        flash('Failed to send email. Please try again or contact support.', 'danger')
    
    return redirect(url_for('projects_report'))

"@

# 4. Add the code to app.py
$appContent = Get-Content -Path "app.py" -Raw

# Replace imports
$appContent = $appContent -replace [regex]::Escape($currentImports), $newImports

# Add the report code before if __name__ == '__main__':
if (-not $appContent.Contains('def projects_report()')) {
    $appContent = $appContent -replace '(?s)if __name__ == ''__main__'':', "$reportCode`n`nif __name__ == '__main__':"
    Set-Content -Path "app.py" -Value $appContent
    Write-Host "Added report routes and functions to app.py" -ForegroundColor Green
} else {
    Write-Host "Report routes already exist in app.py" -ForegroundColor Yellow
}

# 5. Create the report template
$templateDir = "templates"
if (-not (Test-Path $templateDir)) {
    New-Item -ItemType Directory -Path $templateDir | Out-Null
}

$templatePath = Join-Path $templateDir "projects_report.html"
$templateContent = @'
{% extends 'base.html' %}

{% block title %}Projects Allocation Report{% endblock %}

{% block content %}
<div class="container-fluid mt-4">
    <div class="card shadow-sm">
        <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="mb-0">Projects Allocation Report</h5>
            <div>
                <a href="{{ url_for('projects_report', export=1) }}" class="btn btn-success btn-sm">
                    <i class="fas fa-file-excel me-1"></i> Export to Excel
                </a>
                <a href="{{ url_for('projects_report', email=1) }}" class="btn btn-primary btn-sm ms-2">
                    <i class="fas fa-envelope me-1"></i> Email Me
                </a>
            </div>
        </div>
        <div class="card-body">
            <div class="alert alert-info">
                <i class="fas fa-info-circle me-2"></i>
                Report generated on: {{ current_time }}
            </div>
            
            <div class="table-responsive">
                <table class="table table-bordered table-hover">
                    <thead class="table-light">
                        <tr>
                            <th>Project Name</th>
                            <th>Status</th>
                            <th>Service Line</th>
                            <th>Project Type</th>
                            <th>SOW Start</th>
                            <th>SOW End</th>
                            <th>Actual Start</th>
                            <th>Actual End</th>
                            <th>PO Amount</th>
                            <th>SOW Allocation</th>
                            <th>Actual Allocation</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for project in projects %}
                        <tr>
                            <td>{{ project.name }}</td>
                            <td>
                                <span class="badge {{ 'bg-success' if project.status == 'Active' else 'bg-secondary' }}">
                                    {{ project.status or 'Active' }}
                                </span>
                            </td>
                            <td>{{ project.service_line or 'N/A' }}</td>
                            <td>{{ project.project_type or 'N/A' }}</td>
                            <td>{{ project.sow_start_date.strftime('%Y-%m-%d') if project.sow_start_date else 'N/A' }}</td>
                            <td>{{ project.sow_end_date.strftime('%Y-%m-%d') if project.sow_end_date else 'N/A' }}</td>
                            <td>{{ project.actual_start_date.strftime('%Y-%m-%d') if project.actual_start_date else 'N/A' }}</td>
                            <td>{{ project.actual_end_date.strftime('%Y-%m-%d') if project.actual_end_date else 'N/A' }}</td>
                            <td class="text-end">{{ "%.2f"|format(project.po_amount) if project.po_amount else '0.00' }}</td>
                            <td class="text-end">{{ "%.2f"|format(project.sow_allocation_fte) if project.sow_allocation_fte else '0.00' }}</td>
                            <td class="text-end">{{ "%.2f"|format(project.actual_allocation_fte) if project.actual_allocation_fte else '0.00' }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'@

Set-Content -Path $templatePath -Value $templateContent
Write-Host "Created report template: $templatePath" -ForegroundColor Green

# 6. Add navigation link
$baseTemplatePath = Join-Path $templateDir "base.html"
if (Test-Path $baseTemplatePath) {
    $navPattern = '<ul class="navbar-nav me-auto">'
    $navLink = '                <li class="nav-item">\n                    <a class="nav-link" href="{{ url_for(''projects_report'') }}">\n                        <i class="fas fa-chart-pie me-2"></i>Projects Report\n                    </a>\n                </li>'
    
    $baseContent = Get-Content -Path $baseTemplatePath -Raw
    if (-not $baseContent.Contains('url_for(''projects_report'')')) {
        $baseContent = $baseContent -replace [regex]::Escape($navPattern), "$navPattern`n$navLink"
        Set-Content -Path $baseTemplatePath -Value $baseContent
        Write-Host "Added navigation link to base template" -ForegroundColor Green
    } else {
        Write-Host "Navigation link already exists in base template" -ForegroundColor Yellow
    }
} else {
    Write-Host "Could not find base.html to add navigation link" -ForegroundColor Yellow
}

# 7. Install required packages
$requiredPackages = @("pandas", "openpyxl", "xlsxwriter", "flask-mail")
foreach ($pkg in $requiredPackages) {
    pip show $pkg | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing $pkg..."
        pip install $pkg
    }
}

Write-Host @"

====================================================
Projects Report Feature Installation Complete
====================================================

What was done:
1. Created backup: $backupName
2. Added report routes and functions to app.py
3. Created report template: $templatePath
4. Added navigation link to the menu
5. Installed required Python packages

Next Steps:
1. Restart your Flask application
2. Access the report at: /reports/projects
3. Use the Export and Email buttons in the report

Troubleshooting:
- If you see a 404 error, make sure to restart your Flask application
- Check the Flask console for any error messages
- The backup file contains your original app.py

"@