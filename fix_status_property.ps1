# Save this as: C:\apps\resource_planner_web\fix_status_property.ps1

# 1. Backup current models.py
$backupDir = "C:\apps\resource_planner_web\backups\status_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir
Write-Host "Backup created at: $backupDir" -ForegroundColor Cyan

# 2. Add the status property to Project model
$modelsPath = "C:\apps\resource_planner_web\models.py"
$modelsContent = Get-Content $modelsPath -Raw

# Add the status property right before the __repr__ method
$statusProperty = @'

    @property
    def status(self):
        """Return 'Active' or 'Closed' based on end dates"""
        from datetime import date
        today = date.today()
        if (self.sow_end_date and self.sow_end_date < today) or \
           (hasattr(self, 'actual_end_date') and self.actual_end_date and self.actual_end_date < today):
            return 'Closed'
        return 'Active'

'@

# Insert the status property
$modelsContent = $modelsContent -replace '(def __repr__\(self\):\s+return f''<Project {self\\.name}>'')', "$statusProperty`n    `$1"

# Save the changes
$modelsContent | Set-Content $modelsPath -Encoding UTF8
Write-Host "Added status property to Project model" -ForegroundColor Green

# 3. Create a simple test route
$testRoute = @"

# Simple test route
@app.route('/check-project-status')
def check_project_status():
    from models import Project
    project = Project.query.first()
    if project:
        return f"Project: {project.name}, Status: {project.status}"
    return "No projects found"

"@

# Add test route if it doesn't exist
$appPath = "C:\apps\resource_planner_web\app.py"
$appContent = Get-Content $appPath -Raw
if (-not ($appContent -match "@app.route\('/check-project-status'\)")) {
    $appContent = $appContent.TrimEnd() + "`n`n$testRoute"
    $appContent | Set-Content $appPath -Encoding UTF8
    Write-Host "Added test route at /check-project-status" -ForegroundColor Green
}

Write-Host "`n=== Next Steps ===" -ForegroundColor Green
Write-Host "1. Restart your Flask application" -ForegroundColor Yellow
Write-Host "2. Visit /check-project-status to test the status property" -ForegroundColor Yellow
Write-Host "3. The status will be 'Closed' if either sow_end_date or actual_end_date is in the past" -ForegroundColor Yellow