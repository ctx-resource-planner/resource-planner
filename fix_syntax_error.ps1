# Save this as: C:\apps\resource_planner_web\fix_syntax_error.ps1

# 1. Backup current models.py
$backupDir = "C:\apps\resource_planner_web\backups\syntax_fix_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir

Write-Host "Backup created at: $backupDir" -ForegroundColor Green

# 2. Fix the syntax error in models.py
$modelsPath = "C:\apps\resource_planner_web\models.py"
$modelsContent = Get-Content $modelsPath -Raw

# Fix the unterminated docstring
$modelsContent = $modelsContent -replace '(?s)(\s+"""Use this when you need to include inactive employees\.""").*?(\n\s+def)', "`$1`n    pass`n`$2"

# Save the fixed content
$modelsContent | Set-Content $modelsPath -Encoding UTF8

Write-Host "Fixed syntax error in models.py" -ForegroundColor Green
Write-Host "Please restart your Flask application" -ForegroundColor Yellow