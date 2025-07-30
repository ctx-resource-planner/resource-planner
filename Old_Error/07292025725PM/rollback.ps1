# Rollback Script - Project Status Update v1.1
$backupDir = "$args[0]"
if (-not $backupDir) {
    Write-Host "Please provide the backup directory path" -ForegroundColor Red
    exit 1
}

Write-Host "Rolling back changes from backup: $backupDir" -ForegroundColor Cyan

$files = Get-ChildItem -Path $backupDir
foreach ($file in $files) {
    $destPath = Join-Path "C:\apps\resource_planner_web" $file.Name
    if (Test-Path $destPath) {
        Copy-Item -Path $file.FullName -Destination $destPath -Force
        Write-Host "  Restored: $($file.Name)" -ForegroundColor Green
    }
}

Write-Host "
Rollback completed! Please restart your Flask application." -ForegroundColor Green
