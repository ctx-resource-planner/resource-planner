# Save this as: C:\apps\resource_planner_web\update_project_status_ui.ps1

# Backup existing files
$backupDir = "C:\apps\resource_planner_web\backups\status_ui_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

# 1. Update projects list template
$templatePath = "C:\apps\resource_planner_web\templates\projects_list.html"
if (Test-Path $templatePath) {
    Copy-Item $templatePath "$backupDir\projects_list.html"
    $templateContent = Get-Content $templatePath -Raw
    
    # Add status column header
    $templateContent = $templateContent -replace '(</th>\s*<th>Actions</th>)', '$1<th>Status</th>'
    
    # Add status badge to each row
    $templateContent = $templateContent -replace '(<td>\s*<a href="[^"]*" class="[^"]*">[^<]*</a>.*?</td>\s*<td>.*?</td>\s*<td>)', @'
$1
        <td>
            {% if project.status == 'Active' %}
                <span class="badge bg-success">Active</span>
            {% else %}
                <span class="badge bg-secondary">Closed</span>
            {% endif %}
        </td>
'@

    # Add filter buttons above the table
    $templateContent = $templateContent -replace '(<\!-- Add status filter buttons here -->)', @'
<div class="mb-3">
    <a href="?status=all" class="btn btn-sm btn-outline-secondary {% if request.args.get('status') == 'all' %}active{% endif %}">Show All</a>
    <a href="?status=active" class="btn btn-sm btn-outline-secondary {% if not request.args.get('status') == 'all' %}active{% endif %}">Active Only</a>
</div>
'@

    $templateContent | Set-Content $templatePath -Encoding UTF8
    Write-Host "Updated projects list template" -ForegroundColor Green
}

# 2. Update the projects route in app.py
$appPath = "C:\apps\resource_planner_web\app.py"
if (Test-Path $appPath) {
    Copy-Item $appPath "$backupDir\app.py"
    $appContent = Get-Content $appPath -Raw
    
    # Update the projects route to handle status filter
    $appContent = $appContent -replace '(?s)@app\.route\(''/projects''\).*?def projects_list\(\):.*?projects = Project\.query', 
    @'
@app.route('/projects')
def projects_list():
    status_filter = request.args.get('status', 'active')
    query = Project.query
    if status_filter != 'all':
        query = query.filter_by(status='Active')
    projects = query
'@

    $appContent | Set-Content $appPath -Encoding UTF8
    Write-Host "Updated projects route in app.py" -ForegroundColor Green
}

Write-Host "`n=== Update Complete ===" -ForegroundColor Green
Write-Host "1. Files backed up to: $backupDir" -ForegroundColor Cyan
Write-Host "2. Please restart your Flask application" -ForegroundColor Yellow
Write-Host "3. Visit /projects to see the status column and filter buttons" -ForegroundColor Yellow