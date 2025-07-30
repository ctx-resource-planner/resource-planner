# Backup and Update Script for Resource Planner Web App

# Define file paths
$baseDir = "C:\apps\resource_planner_web"
$modelsPath = Join-Path $baseDir "models.py"
$appPath = Join-Path $baseDir "app.py"
$backupDir = Join-Path $baseDir "backups"

# Create backup directory if it doesn't exist
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}

# Create timestamp for backup files
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Function to create backup
function Backup-File {
    param($filePath)
    $backupPath = Join-Path $backupDir "$(Split-Path $filePath -Leaf).$timestamp.bak"
    Copy-Item $filePath $backupPath -Force
    return $backupPath
}

try {
    # Backup original files
    $modelsBackup = Backup-File $modelsPath
    $appBackup = Backup-File $appPath
    
    Write-Host "Backups created:"
    Write-Host "- Models: $modelsBackup"
    Write-Host "- App: $appBackup"
    Write-Host ""

    # 1. Update models.py
    Write-Host "Updating models.py..."
    $modelsContent = Get-Content $modelsPath -Raw
    
    # Add get_active class method to Employee model
    $employeeModelPattern = '(class Employee\(db\.Model\):[\s\S]*?def __repr__\(self\):[\s\S]*?return f"<Employee {self.name}>")'
    $employeeModelReplacement = @'
$1

    @classmethod
    def get_active(cls):
        """Return a query with active employees only."""
        return cls.query.filter_by(is_active=True)
'@
    $modelsContent = $modelsContent -replace $employeeModelPattern, $employeeModelReplacement
    
    # Save updated models.py
    Set-Content -Path $modelsPath -Value $modelsContent
    Write-Host "- Added get_active() class method to Employee model"

    # 2. Update app.py
    Write-Host "`nUpdating app.py..."
    $appContent = Get-Content $appPath -Raw
    
    # Update the index route
    $indexRoutePattern = '@app\.route\([''"]/[''"]'
    $indexRouteMatch = [regex]::Match($appContent, "$indexRoutePattern.*?def index\(\):.*?(?=@app\.route|$)", [System.Text.RegularExpressions.RegexOptions]::Singleline)
    
    if ($indexRouteMatch.Success) {
        $indexRoute = $indexRouteMatch.Value
        $updatedIndexRoute = $indexRoute -replace 'employees_for_dropdown = Employee\.query\.filter_by\(is_active=True\)\.order_by\(Employee\.name\)\.all\(\)', 
                                                 'employees_for_dropdown = Employee.get_active().order_by(Employee.name).all()'
        
        $appContent = $appContent.Replace($indexRoute, $updatedIndexRoute)
        Write-Host "- Updated index route to use Employee.get_active()"
    } else {
        Write-Host "Warning: Could not find index route to update" -ForegroundColor Yellow
    }

    # Update the allocations route
    $allocationsRoutePattern = '@app\.route\([''"]/allocations[''"]'
    $allocationsRouteMatch = [regex]::Match($appContent, "$allocationsRoutePattern.*?def allocations_list\(\):.*?(?=@app\.route|$)", [System.Text.RegularExpressions.RegexOptions]::Singleline)
    
    if ($allocationsRouteMatch.Success) {
        $allocationsRoute = $allocationsRouteMatch.Value
        $updatedAllocationsRoute = $allocationsRoute -replace 'Allocation\.query', 'Allocation.query.join(Employee).filter(Employee.is_active == True)'
        
        $appContent = $appContent.Replace($allocationsRoute, $updatedAllocationsRoute)
        Write-Host "- Updated allocations route to filter out inactive employees"
    } else {
        Write-Host "Warning: Could not find allocations route to update" -ForegroundColor Yellow
    }

    # Save updated app.py
    Set-Content -Path $appPath -Value $appContent

    Write-Host "`nUpdate complete! Please review the changes and restart your Flask application."
    Write-Host "Backups were created in: $backupDir" -ForegroundColor Green

} catch {
    Write-Host "An error occurred: $_" -ForegroundColor Red
    Write-Host "Restoring from backups..." -ForegroundColor Yellow
    
    # Restore from backups if they exist
    if (Test-Path $modelsBackup) { Copy-Item $modelsBackup $modelsPath -Force }
    if (Test-Path $appBackup) { Copy-Item $appBackup $appPath -Force }
    
    Write-Host "Files have been restored to their original state." -ForegroundColor Green
}