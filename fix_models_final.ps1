# Save this as: C:\apps\resource_planner_web\fix_models_final.ps1

# 1. Backup current models.py
$backupDir = "C:\apps\resource_planner_web\backups\models_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir

# 2. Read the file content
$modelsPath = "C:\apps\resource_planner_web\models.py"
$content = Get-Content $modelsPath -Raw

# 3. Fix the include_inactive function and clean up
$newContent = $content -replace '(?s)# Add a method to include inactive employees when needed\s+def include_inactive\(query\):.*?return query\.execution_options\(include_inactive=True\)\s+', @'
# Add a method to include inactive employees when needed
def include_inactive(query):
    """Use this when you need to include inactive employees."""
    return query.execution_options(include_inactive=True)

'@

# 4. Ensure the Project status property is properly formatted
$newContent = $newContent -replace '(?s)# Quick fix for project status - Add this at the bottom of models\.py\s+Project\.status = property\(lambda self:.*?\)\s*', @'
# Project status property
Project.status = property(lambda self: 'Active' if not self.sow_end_date or self.sow_end_date >= __import__('datetime').date.today() else 'Closed')

'@

# 5. Save the fixed content
$newContent | Set-Content $modelsPath -Encoding UTF8

Write-Host "Fixed the syntax errors in models.py" -ForegroundColor Green
Write-Host "Backup saved to: $backupDir" -ForegroundColor Cyan
Write-Host "Please try running the Flask application again" -ForegroundColor Yellow