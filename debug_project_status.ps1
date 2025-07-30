# Save this as: C:\apps\resource_planner_web\debug_project_status.ps1

# 1. Check if the Project model has the status property
Write-Host "=== Checking Project Model ===" -ForegroundColor Cyan
Get-Content "C:\apps\resource_planner_web\models.py" | Select-String -Pattern "class Project" -Context 0,30 | Select-String -Pattern "status|sow_end_date"

# 2. Check the projects list template
$projectsTemplate = Get-ChildItem -Path "C:\apps\resource_planner_web\templates" -Filter "*project*list*.html" -Recurse -File | Select-Object -First 1
if ($projectsTemplate) {
    Write-Host "`n=== Checking Projects Template ===" -ForegroundColor Cyan
    Get-Content $projectsTemplate.FullName | Select-String -Pattern "status|badge|sow_end_date" -Context 0,5
}

# 3. Check the projects list route
Write-Host "`n=== Checking Projects Route ===" -ForegroundColor Cyan
Get-Content "C:\apps\resource_planner_web\app.py" | Select-String -Pattern "@app\.route\(['""]/projects['""]\)" -Context 0,20

# 4. Check the actual data in the database
Write-Host "`n=== Checking Project Data ===" -ForegroundColor Cyan
Write-Host "To check project data, please run these commands in your Flask shell:"
@"
from datetime import date
from app import app, db
from models import Project

with app.app_context():
    projects = Project.query.all()
    for p in projects:
        status = 'Active' if not p.sow_end_date or p.sow_end_date >= date.today() else 'Closed'
        print(f"Project: {p.name:<40} | End Date: {p.sow_end_date} | Status: {status}")
"@ | Out-File "check_projects.py" -Encoding UTF8

Write-Host "`nTo check project data, run these commands in your terminal:" -ForegroundColor Yellow
Write-Host "1. flask shell" -ForegroundColor White
Write-Host "2. Copy and paste the code above into the shell" -ForegroundColor White
Write-Host "3. Or run: python -c ""`$(Get-Content check_projects.py)""" -ForegroundColor White

# 5. Quick fix - let's add the status property directly
Write-Host "`n=== Applying Quick Fix ===" -ForegroundColor Cyan
$quickFix = @"

# Quick fix for project status - Add this at the bottom of models.py
Project.status = property(lambda self: 'Active' if not self.sow_end_date or self.sow_end_date >= __import__('datetime').date.today() else 'Closed')
"@

Add-Content -Path "C:\apps\resource_planner_web\models.py" -Value $quickFix
Write-Host "Added quick status property to Project model" -ForegroundColor Green

Write-Host "`nPlease restart your Flask application and check if the status appears now." -ForegroundColor Yellow