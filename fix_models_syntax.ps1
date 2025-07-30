# Save this as: C:\apps\resource_planner_web\fix_models_syntax.ps1

# Backup the current models.py
$backupDir = "C:\apps\resource_planner_web\backups\models_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir

# Read the file content
$modelsContent = Get-Content "C:\apps\resource_planner_web\models.py" -Raw

# Fix the include_inactive function's docstring
$fixedContent = $modelsContent -replace '(?s)(def include_inactive\(query\):\s+)(""".*?""")?', @'
def include_inactive(query):
    """Use this when you need to include inactive employees."""
    return query.execution_options(include_inactive=True)

'@

# Save the fixed content
$fixedContent | Set-Content "C:\apps\resource_planner_web\models.py" -Encoding UTF8

Write-Host "Fixed the syntax error in models.py" -ForegroundColor Green
Write-Host "Please try running the Flask application again" -ForegroundColor Yellow