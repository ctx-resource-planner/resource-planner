# setup_tests.ps1 - Minimal test setup script

# Configuration
$projectRoot = "C:\apps\resource_planner_web"
$testDir = "$projectRoot\tests"

# Create test directory
New-Item -ItemType Directory -Path $testDir -Force | Out-Null

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "âœ… Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "âŒ Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Install required packages
$packages = @("playwright", "pytest")
foreach ($pkg in $packages) {
    Write-Host "Installing $pkg..." -NoNewline
    pip install $pkg
    if ($LASTEXITCODE -ne 0) {
        Write-Host " âŒ" -ForegroundColor Red
        Write-Host "Failed to install $pkg" -ForegroundColor Red
        exit 1
    }
    Write-Host " âœ“" -ForegroundColor Green
}

# Install Playwright browsers
Write-Host "Installing Playwright browsers..." -NoNewline
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Write-Host " âŒ" -ForegroundColor Red
    Write-Host "Failed to install Playwright browsers" -ForegroundColor Red
    exit 1
}
Write-Host " âœ“" -ForegroundColor Green

Write-Host "`nâœ… Basic setup complete!" -ForegroundColor Green
Write-Host "Creating test directory structure..." -NoNewline

# Create basic directory structure
$dirs = @(
    "$testDir\pages",
    "$testDir\fixtures",
    "$testDir\screenshots",
    "$testDir\reports",
    "$testDir\logs"
)

$dirs | ForEach-Object { 
    New-Item -ItemType Directory -Path $_ -Force | Out-Null 
}

Write-Host " âœ“" -ForegroundColor Green
Write-Host "`nðŸŽ‰ Test environment setup complete!" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "1. Create test_config.py with your test settings"
Write-Host "2. Create base_test.py with your test base class"
Write-Host "3. Start writing your test files in the tests directory"
