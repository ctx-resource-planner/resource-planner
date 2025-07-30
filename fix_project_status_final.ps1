# Save this as: C:\apps\resource_planner_web\fix_project_status_final.ps1

# 1. Backup current files
$backupDir = "C:\apps\resource_planner_web\backups\project_status_final_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir

Write-Host "Backup created at: $backupDir" -ForegroundColor Green

# 2. Update models.py - Update status property to check both end dates
$modelsPath = "C:\apps\resource_planner_web\models.py"
$modelsContent = Get-Content $modelsPath -Raw

# Remove any existing status property
$modelsContent = $modelsContent -replace '(?s)\s+@property\s+def status\(self\):.*?return ''Active''\s+', "`n"

# Add the updated status property
$statusProperty = @'

    @property
    def status(self):
        """Return 'Active' or 'Closed' based on project end dates (sow_end_date or actual_end_date)"""
        from datetime import date
        today = date.today()
        
        # Check if either end date is in the past
        if (hasattr(self, 'sow_end_date') and self.sow_end_date and self.sow_end_date < today) or \
           (hasattr(self, 'actual_end_date') and self.actual_end_date and self.actual_end_date < today):
            return 'Closed'
        return 'Active'

'@

# Add status property after the Project class definition
$modelsContent = $modelsContent -replace '(class Project\(db\.Model\):.*?def __repr__\(self\):\s+return f''<Project {self\.name}>'')', 
"`$1`n$statusProperty"

$modelsContent | Set-Content $modelsPath -Encoding UTF8
Write-Host "Updated models.py with dual-date status check" -ForegroundColor Green

# 3. Create a test route to verify the status
$testRoute = @"

# Test route to verify project status with both dates
@app.route('/test-project-status')
def test_project_status():
    from datetime import date, timedelta
    from models import Project, db
    
    # Get all projects with their status
    projects = Project.query.all()
    status_report = []
    
    for project in projects:
        status = project.status
        sow_status = f"sow_end_date: {project.sow_end_date}" if project.sow_end_date else "No sow_end_date"
        actual_status = f"actual_end_date: {project.actual_end_date}" if project.actual_end_date else "No actual_end_date"
        status_report.append(f"Project: {project.name:<40} | {sow_status:<25} | {actual_status:<25} | Status: {status}")
    
    return "<pre>" + "\n".join(status_report) + "</pre>"

"@

# Add test route if it doesn't exist
$appPath = "C:\apps\resource_planner_web\app.py"
if (-not (Get-Content $appPath -Raw).Contains("@app.route('/test-project-status')")) {
    Add-Content -Path $appPath -Value "`n$testRoute"
    Write-Host "Added test route at /test-project-status" -ForegroundColor Green
}

# 4. Verify the projects list template has the status column
$projectsTemplate = Get-ChildItem -Path "C:\apps\resource_planner_web\templates" -Filter "*project*list*.html" -Recurse -File | Select-Object -First 1

if ($projectsTemplate) {
    $templateContent = Get-Content $projectsTemplate.FullName -Raw
    
    # Check if status column exists
    if (-not ($templateContent -match "status")) {
        # Add status column header
        $templateContent = $templateContent -replace '(</th>\s*<th>Actions</th>)', '$1<th>Status</th>'
        
        # Add status badge to each project row
        $templateContent = $templateContent -replace '(<td>\s*<a href="[^"]*" class="[^"]*">[^<]*</a>.*?</td>\s*</tr>)', @'
$1
        <td>
            {% if project.status == 'Active' %}
                <span class="badge bg-success">Active</span>
            {% else %}
                <span class="badge bg-secondary">Closed</span>
            {% endif %}
        </td>
    </tr>
'@
        $templateContent | Set-Content $projectsTemplate.FullName -Encoding UTF8
        Write-Host "Updated $($projectsTemplate.Name) with status column" -ForegroundColor Green
    } else {
        Write-Host "Status column already exists in template" -ForegroundColor Yellow
    }
}

Write-Host "`n=== Update Complete ===" -ForegroundColor Green
Write-Host "1. Restart your Flask application" -ForegroundColor Yellow
Write-Host "2. Visit /test-project-status to verify project statuses" -ForegroundColor Yellow
Write-Host "3. Check the projects list page to see the status badges" -ForegroundColor Yellow
Write-Host "   - Green badge: Project is active (no end dates in past)" -ForegroundColor Green
Write-Host "   - Gray badge: Project is closed (either sow_end_date or actual_end_date is in past)" -ForegroundColor Gray