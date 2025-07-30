# Project Status Update Script v1.1 - PowerShell 2.0 Compatible
$version = "1.1"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "C:\apps\resource_planner_web\backups\status_update_v${version}_$timestamp"

# Create backup directory
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

# Files we'll be modifying
$filesToBackup = @(
    "C:\apps\resource_planner_web\models.py",
    "C:\apps\resource_planner_web\app.py",
    "C:\apps\resource_planner_web\templates\projects_list.html"
)

function Write-Status {
    param([string]$message, [string]$color = "White")
    Write-Host $message -ForegroundColor $color
}

Write-Status "Creating backup of files..." "Cyan"
foreach ($file in $filesToBackup) {
    if (Test-Path $file) {
        $backupPath = Join-Path $backupDir (Split-Path $file -Leaf)
        Copy-Item -Path $file -Destination $backupPath -Force
        Write-Status "  Backed up: $file" "Green"
    }
}

# 1. Update models.py
Write-Status "`nUpdating models.py..." "Cyan"
$statusProperty = @'

    @property
    def status(self):
        """Return 'Active' or 'Closed' based on project end date"""
        if hasattr(self, 'end_date') and self.end_date:
            from datetime import date
            return 'Active' if self.end_date >= date.today() else 'Closed'
        return 'Active'
'@

$modelsPath = "C:\apps\resource_planner_web\models.py"
(Get-Content $modelsPath) -replace '(class Project\(db\.Model\):.*?)(\n\s+def)', "`$1$statusProperty`n`$2" | Set-Content $modelsPath -Encoding UTF8

# 2. Update app.py
Write-Status "Updating app.py..." "Cyan"
$appPath = "C:\apps\resource_planner_web\app.py"
$appContent = Get-Content $appPath -Raw

# Add date import if not present
if (-not ($appContent -match "from datetime import date")) {
    $appContent = $appContent -replace '(from\s+flask\s+import\s+.*?)(\n|$)', "`$1, date`n"
}

# Update projects list route
$projectsRouteUpdate = @'

    # Filter out closed projects unless show_all is set
    if not request.args.get('show_all') == 'yes':
        projects = projects.filter(Project.end_date >= date.today())
'@

$appContent = $appContent -replace '(projects\s*=\s*Project\.query.*?)(\n\s+return\s+render_template)', "`$1$projectsRouteUpdate`n`$2"
$appContent | Set-Content -Path $appPath -Encoding UTF8

# 3. Update projects_list.html
Write-Status "Updating projects_list.html..." "Cyan"
$projectsTemplate = Get-ChildItem -Path "C:\apps\resource_planner_web\templates" -Filter "*project*list*.html" -Recurse | Select-Object -First 1

if ($projectsTemplate) {
    $templateContent = Get-Content $projectsTemplate.FullName -Raw
    
    # Add Status column header
    $templateContent = $templateContent -replace '(</th>\s*<th>Actions</th>)', '${1}<th>Status</th>'
    
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

    # Add filter dropdown
    $filterHtml = @'
    <div class="mb-3">
        <form method="get" class="d-flex gap-2">
            <select name="show_all" class="form-select" style="width: auto;" onchange="this.form.submit()">
                <option value="no" {% if not request.args.get('show_all') == 'yes' %}selected{% endif %}>Show Active Projects</option>
                <option value="yes" {% if request.args.get('show_all') == 'yes' %}selected{% endif %}>Show All Projects</option>
            </select>
        </form>
    </div>
'@
    $templateContent = $templateContent -replace '(<!-- Add any filter controls here -->)', $filterHtml
    $templateContent | Set-Content -Path $projectsTemplate.FullName -Encoding UTF8
}

# Create rollback script
$rollbackScript = @"
# Rollback Script - Project Status Update v$version
`$backupDir = "`$args[0]"
if (-not `$backupDir) {
    Write-Host "Please provide the backup directory path" -ForegroundColor Red
    exit 1
}

Write-Host "Rolling back changes from backup: `$backupDir" -ForegroundColor Cyan

`$files = Get-ChildItem -Path `$backupDir
foreach (`$file in `$files) {
    `$destPath = Join-Path "C:\apps\resource_planner_web" `$file.Name
    if (Test-Path `$destPath) {
        Copy-Item -Path `$file.FullName -Destination `$destPath -Force
        Write-Host "  Restored: `$(`$file.Name)" -ForegroundColor Green
    }
}

Write-Host "`nRollback completed! Please restart your Flask application." -ForegroundColor Green
"@

$rollbackScript | Out-File "C:\apps\resource_planner_web\rollback.ps1" -Encoding UTF8

Write-Status "`nUpdate completed!" "Green"
Write-Status "Backup saved to: $backupDir" "Cyan"
Write-Status "`nTo rollback changes, run:" "Yellow"
Write-Host "  .\rollback.ps1 $backupDir" -ForegroundColor White -BackgroundColor DarkGray
Write-Status "`nPlease restart your Flask application for changes to take effect." "Yellow"