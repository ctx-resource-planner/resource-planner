# 1. Create backup
$backupName = "app_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').py"
Copy-Item -Path "app.py" -Destination $backupName
Write-Host "Backup created: $backupName" -ForegroundColor Green

# 2. Get current function content
$startMarker = "@app.route('/projects')"
$endMarker = "return render_template('projects_list.html', projects=projects)"

$content = Get-Content -Path "app.py" -Raw
$startIndex = $content.IndexOf($startMarker)
$endIndex = $content.IndexOf($endMarker, $startIndex) + $endMarker.Length
$functionContent = $content.Substring($startIndex, $endIndex - $startIndex)

# 3. Create new function content
$newFunction = @"
@app.route('/projects')
@login_required
def projects_list():
    try:
        # Get all projects with their allocations
        projects = Project.query.options(joinedload(Project.allocations)).all()
        
        # Calculate total allocation for each project
        for project in projects:
            # Sum up all allocation percentages for this project
            total_allocation = sum(
                allocation.billable_allocation_percentage / 100.0  # Convert percentage to decimal
                for allocation in project.allocations
                if allocation.billable_allocation_percentage is not None
            )
            project.actual_allocation_fte = round(total_allocation, 2) if total_allocation else 0

        # Debug info
        print(f"Found {len(projects)} projects")
        for i, p in enumerate(projects[:3], 1):  # Print first 3 for debugging
            print(f"Project {i}: {getattr(p, 'name', 'No name')}, Allocation: {getattr(p, 'actual_allocation_fte', 0)}")

        return render_template('projects_list.html', projects=projects)
    except Exception as e:
        print(f"Error in projects_list: {str(e)}")
        flash('An error occurred while loading projects.', 'danger')
        return render_template('projects_list.html', projects=[])
"@

# 4. Replace the function
$newContent = $content.Remove($startIndex, $endIndex - $startIndex).Insert($startIndex, $newFunction)

# 5. Save changes
$newContent | Set-Content -Path "app.py" -NoNewline
Write-Host "File updated successfully" -ForegroundColor Green

# 6. Create restore script
$restoreCmd = "Copy-Item -Path `"$backupName`" -Destination `"app.py`" -Force"
$restoreScript = "# To restore from backup, run:`r`n$restoreCmd"
$restoreScript | Out-File -FilePath "restore_backup.ps1" -Force
Write-Host "Restore script created: restore_backup.ps1" -ForegroundColor Cyan

# 7. Verify changes
if ((Get-Content -Path "app.py" -Raw) -match "project.actual_allocation_fte") {
    Write-Host "Changes verified successfully" -ForegroundColor Green
    Write-Host "`nPlease restart your Flask application for changes to take effect" -ForegroundColor Cyan
} else {
    Write-Host "Changes not detected. Restoring backup..." -ForegroundColor Red
    Invoke-Expression $restoreCmd
    Write-Host "Original file restored from backup" -ForegroundColor Green
}