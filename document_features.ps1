# Create output directory if it doesn't exist
$outputDir = "C:\apps\features_documentation\Prod"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

# Generate timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Output file path with timestamp
$outputFile = "$outputDir\features_documentation_$timestamp.txt"

# Run the documentation script and save to file
@"

=== DOCUMENTATION GENERATED ON: $(Get-Date) ===

"@ | Out-File -FilePath $outputFile -Encoding utf8

# 1. Find all routes in the application
@"

=== APPLICATION ROUTES ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Select-String -Path "C:\apps\resource_planner_web\app.py" -Pattern "@app\.route\(['`"]([^'`"]+)['`"]" | 
    ForEach-Object { 
        $route = $_.Matches.Groups[1].Value
        $line = $_.LineNumber
        $method = if ($_.Line -match "methods=\[([^\]]+)\]") { $matches[1] } else { "GET" }
        "ROUTE: $route (Line: $line, Method: $method)"
    } | Out-File -FilePath $outputFile -Append -Encoding utf8

# 2. Find database models
@"

=== DATABASE MODELS ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Select-String -Path "C:\apps\resource_planner_web\models.py" -Pattern "class\s+(\w+)\(db\.Model\)" |
    ForEach-Object { $_.Matches.Groups[1].Value } |
    Out-File -FilePath $outputFile -Append -Encoding utf8

# 3. Find utility functions
@"

=== UTILITY FUNCTIONS ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Select-String -Path "C:\apps\resource_planner_web\*.py" -Pattern "def\s+([a-z_]+)\s*\(" |
    Where-Object { $_.Path -notlike "*__init__.py" -and $_.Line -notmatch "^\s*def\s+test_" } |
    ForEach-Object { $_.Matches.Groups[1].Value } |
    Sort-Object -Unique |
    Out-File -FilePath $outputFile -Append -Encoding utf8

# 4. Find templates
@"

=== TEMPLATES ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Get-ChildItem -Path "C:\apps\resource_planner_web\templates" -Recurse -File |
    Where-Object { $_.Extension -match "\.html|\.js" } |
    Select-Object -ExpandProperty FullName |
    ForEach-Object { $_.Replace('C:\apps\resource_planner_web\', '') } |
    Out-File -FilePath $outputFile -Append -Encoding utf8

# 5. Find API endpoints
@"

=== API ENDPOINTS ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Select-String -Path "C:\apps\resource_planner_web\*.py" -Pattern "@app\.route\(['`"]/api/" |
    ForEach-Object { 
        "ENDPOINT: $($_.Line.Trim())"
        "Location: $($_.Path):$($_.LineNumber)"
        ""
    } | Out-File -FilePath $outputFile -Append -Encoding utf8

# 6. Find background tasks
@"

=== BACKGROUND TASKS ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Select-String -Path "C:\apps\resource_planner_web\*.py" -Pattern "Thread\(|celery\.task" |
    ForEach-Object { 
        "TASK: $($_.Line.Trim())"
        "Location: $($_.Path):$($_.LineNumber)"
        ""
    } | Out-File -FilePath $outputFile -Append -Encoding utf8

# 7. Find scheduled jobs
@"

=== SCHEDULED JOBS ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

Select-String -Path "C:\apps\resource_planner_web\*.py" -Pattern "schedule\.every|@scheduler" |
    ForEach-Object { 
        "JOB: $($_.Line.Trim())"
        "Location: $($_.Path):$($_.LineNumber)"
        ""
    } | Out-File -FilePath $outputFile -Append -Encoding utf8

# 8. Find external integrations
@"

=== EXTERNAL INTEGRATIONS ===
"@ | Out-File -FilePath $outputFile -Append -Encoding utf8

$integrations = @{
    "Email" = "flask_mail"
    "Database" = "SQLAlchemy"
    "Authentication" = "flask_login"
    "API" = "flask_restful|flask_restx"
    "Caching" = "flask_caching|flask_caching"
    "Background Tasks" = "celery|rq"
}

$integrations.GetEnumerator() | ForEach-Object {
    $found = Select-String -Path "C:\apps\resource_planner_web\*.py" -Pattern $_.Value
    if ($found) {
        "INTEGRATION: $($_.Key)" | Out-File -FilePath $outputFile -Append -Encoding utf8
        $found | Select-Object -First 1 | ForEach-Object {
            "  Found in: $($_.Path):$($_.LineNumber)" | Out-File -FilePath $outputFile -Append -Encoding utf8
        }
    }
}

Write-Host "Documentation generated successfully at: $outputFile" -ForegroundColor Green