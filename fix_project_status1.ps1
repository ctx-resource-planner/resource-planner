# Save this as: C:\apps\resource_planner_web\fix_project_status.ps1

# 1. Create backup
$backupDir = "C:\apps\resource_planner_web\backups\project_status_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir
Copy-Item "C:\apps\resource_planner_web\app.py" $backupDir
Write-Host "Created backup in: $backupDir" -ForegroundColor Cyan

# 2. Fix models.py - Add status property to Project model
$modelsPath = "C:\apps\resource_planner_web\models.py"
$modelsContent = Get-Content $modelsPath -Raw

# Add status property before __repr__ method
$statusProperty = @'

    @property
    def status(self):
        """Return 'Active' or 'Closed' based on project end dates"""
        from datetime import date
        today = date.today()
        
        # Check if either end date is in the past
        if (hasattr(self, 'sow_end_date') and self.sow_end_date and self.sow_end_date < today) or \
           (hasattr(self, 'actual_end_date') and self.actual_end_date and self.actual_end_date < today):
            return 'Closed'
        return 'Active'

'@

# Insert the status property
$modelsContent = $modelsContent -replace '(def __repr__\(self\):\s+return f''<Project {self\\.name}>'')', "$statusProperty`n    `$1"
$modelsContent | Set-Content $modelsPath -Encoding UTF8
Write-Host "Added status property to Project model" -ForegroundColor Green

# 3. Update or create test route in app.py
$appPath = "C:\apps\resource_planner_web\app.py"
$testRoute = @"

# Test route to verify project status
@app.route('/test-project-status')
def test_project_status():
    from models import Project
    from datetime import date
    
    projects = Project.query.all()
    result = ["<h2>Project Status Report</h2>"]
    result.append("<style>table {border-collapse: collapse; width: 100%;} th, td {border: 1px solid #ddd; padding: 8px; text-align: left;} th {background-color: #f2f2f2;}</style>")
    result.append("<table><tr><th>Project</th><th>SOW End Date</th><th>Actual End Date</th><th>Status</th></tr>")
    
    for p in projects:
        row = f"<tr><td>{p.name}</td>"
        row += f"<td>{p.sow_end_date or 'None'}</td>"
        row += f"<td>{p.actual_end_date or 'None'}</td>"
        status = p.status
        status_color = "green" if status == "Active" else "gray"
        row += f"<td><span style='color: {status_color}; font-weight: bold;'>{status}</span></td></tr>"
        result.append(row)
    
    result.append("</table>")
    return "<br>".join(result)

"@

# Remove existing test route if it exists
$appContent = Get-Content $appPath -Raw
$appContent = $appContent -replace "(?s)# Test route to verify project status.*?@app\.route\('/test-project-status'\).*?def test_project_status\(\):.*?return.*?\n", ""

# Add the test route at the end of the file
$appContent = $appContent.TrimEnd() + "`n`n$testRoute"
$appContent | Set-Content $appPath -Encoding UTF8
Write-Host "Updated test route at /test-project-status" -ForegroundColor Green

# 4. Update projects list template
$projectsTemplate = Get-ChildItem -Path "C:\apps\resource_planner_web\templates" -Filter "*project*list*.html" -Recurse -File | Select-Object -First 1

if ($projectsTemplate) {
    $templateContent = Get-Content $projectsTemplate.FullName -Raw
    
    # Add Status column header if it doesn't exist
    if (-not ($templateContent -match "Status</th>")) {
        $templateContent = $templateContent -replace '(</th>\s*<th>Actions</th>)', '$1<th>Status</th>'
    }
    
    # Add status badge to each project row if it doesn't exist
    if (-not ($templateContent -match "project.status")) {
        $templateContent = $templateContent -replace '(<td>\s*<a href="[^"]*" class="[^"]*">[^<]*</a>.*?</td>\s*<td>.*?</td>\s*<td>.*?</td>\s*<td>)', '$1<td>{% if project.status == "Active" %}<span class="badge bg-success">Active</span>{% else %}<span class="badge bg-secondary">Closed</span>{% endif %}</td>'
    }
    
    $templateContent | Set-Content $projectsTemplate.FullName -Encoding UTF8
    Write-Host "Updated template: $($projectsTemplate.Name)" -ForegroundColor Green
} else {
    Write-Host "Warning: Could not find projects list template" -ForegroundColor Yellow
}

Write-Host "`n=== Fix Complete ===" -ForegroundColor Green
Write-Host "1. Please restart your Flask application" -ForegroundColor Yellow
Write-Host "2. Visit /test-project-status to verify project statuses" -ForegroundColor Yellow
Write-Host "3. Check the projects list page to see the status badges" -ForegroundColor Yellow
Write-Host "`nBackup location: $backupDir" -ForegroundColor Cyan