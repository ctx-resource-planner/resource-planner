param(
    [string]$browser = "chromium",
    [switch]$headless = $true,
    [switch]$cleanup = $true
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logDir = "$projectRoot\tests\logs"
$reportDir = "$projectRoot\tests\reports"
$screenshotDir = "$projectRoot\tests\screenshots"

# Create directories if they don't exist
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
New-Item -ItemType Directory -Path $screenshotDir -Force | Out-Null

$logFile = "$logDir\test_run_$timestamp.log"
Start-Transcript -Path $logFile -Force

try {
    # Set environment variables
    $env:FLASK_ENV = "testing"
    $env:TESTING = "true"
    $env:TEST_TIMESTAMP = $timestamp

    # Clean previous test database
    if (Test-Path "$projectRoot\instance\test_resource_planner.db") {
        Remove-Item "$projectRoot\instance\test_resource_planner.db"
    }

    # Start Flask app in background
    Write-Host "Starting Flask application..." -ForegroundColor Cyan
    $flaskProcess = Start-Process python -ArgumentList "app.py" -PassThru -NoNewWindow
    
    # Wait for app to start
    Start-Sleep -Seconds 5

    # Run tests
    Write-Host "`nðŸš€ Running tests..." -ForegroundColor Cyan
    $htmlReport = "$reportDir\test_report_$timestamp.html"
    
    # Install test dependencies
    pip install pytest-playwright pytest-html
    
    # Run pytest with HTML report
    $pytestArgs = @(
        "$projectRoot\tests",
        "--browser", $browser
    )
    
    if ($headless) {
        $pytestArgs += "--headless"
    }
    
    $pytestArgs += @(
        "--html=$htmlReport",
        "--self-contained-html",
        "--screenshot=on",
        "--screenshot-dir=$screenshotDir"
    )
    
    python -m pytest @pytestArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Host "âŒ Some tests failed" -ForegroundColor Red
    } else {
        Write-Host "âœ… All tests passed!" -ForegroundColor Green
    }

    # Open the HTML report
    if (Test-Path $htmlReport) {
        Start-Process $htmlReport
    }

} catch {
    Write-Host "âŒ Error running tests: $_" -ForegroundColor Red
    throw
} finally {
    # Stop Flask app
    if ($flaskProcess -and -not $flaskProcess.HasExited) {
        Write-Host "Stopping Flask application..." -ForegroundColor Cyan
        Stop-Process -Id $flaskProcess.Id -Force
    }

    # Run cleanup
    if ($cleanup) {
        Write-Host "`nðŸ§¹ Cleaning up test data..." -ForegroundColor Yellow
        python "$projectRoot\tests\cleanup_test_data.py" 1
    }

    Stop-Transcript
    Write-Host "`nðŸ“‹ Log file: $logFile" -ForegroundColor Cyan
    if (Test-Path $htmlReport) {
        Write-Host "ðŸ“Š Test report: $htmlReport" -ForegroundColor Cyan
    }
}
