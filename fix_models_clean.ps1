# Save this as: C:\apps\resource_planner_web\fix_models_clean.ps1

# 1. Backup current models.py
$backupDir = "C:\apps\resource_planner_web\backups\models_clean_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item "C:\apps\resource_planner_web\models.py" $backupDir

# 2. Get the content before and after the problematic section
$modelsPath = "C:\apps\resource_planner_web\models.py"
$content = Get-Content $modelsPath -Raw

# 3. Extract the part before the include_inactive function
$before = $content -split '(?=def include_inactive\()' | Select-Object -First 1

# 4. Create the corrected include_inactive function
$fixedFunction = @'

# Add a method to include inactive employees when needed
def include_inactive(query):
    """Use this when you need to include inactive employees."""
    return query.execution_options(include_inactive=True)

# Project status property
Project.status = property(lambda self: 'Active' if not self.sow_end_date or self.sow_end_date >= __import__('datetime').date.today() else 'Closed')

'@

# 5. Extract the part after the include_inactive function
$after = $content -split '(?s)def include_inactive\(query\):.*?return query\.execution_options\(include_inactive=True\)' | Select-Object -Last 1
$after = $after -replace '(?s)return query\.execution_options\(include_inactive=True\).*?(\n\s*#|\Z)', "`n"

# 6. Combine the parts
$newContent = $before.TrimEnd() + "`n`n" + $fixedFunction.Trim() + "`n`n" + $after.TrimStart()

# 7. Save the fixed content
$newContent | Set-Content $modelsPath -Encoding UTF8

Write-Host "Cleaned up models.py" -ForegroundColor Green
Write-Host "Backup saved to: $backupDir" -ForegroundColor Cyan
Write-Host "Please try running the Flask application again" -ForegroundColor Yellow