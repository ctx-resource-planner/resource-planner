<#
.SYNOPSIS
    Creates test directory structure and files
#>

$projectRoot = "C:\apps\resource_planner_web"
$testDir = "$projectRoot\tests"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Create directories
$dirs = @(
    "$testDir\pages",
    "$testDir\fixtures",
    "$testDir\screenshots",
    "$testDir\reports",
    "$testDir\logs"
)

Write-Host "📁 Creating directory structure..." -NoNewline
$dirs | ForEach-Object { 
    New-Item -ItemType Directory -Path $_ -Force | Out-Null 
}
Write-Host " ✓" -ForegroundColor Green

# Create test configuration
@"
# test_config.py
TEST_CONFIG = {
    "base_url": "http://localhost:5000",
    "credentials": {
        "admin_user": "admin",
        "admin_pass": "admin"  # Change to use environment variable in production
    },
    "test_data": {
        "prefix": "test_$timestamp",
        "employee": {
            "name": "Test User",
            "email": "test_$timestamp@example.com",
            "position": "Tester"
        }
    }
}
"@ | Out-File -FilePath "$testDir\test_config.py" -Encoding utf8

Write-Host "✅ Test structure created!" -ForegroundColor Green
Write-Host "Run the next script: .\setup_base_test.ps1"