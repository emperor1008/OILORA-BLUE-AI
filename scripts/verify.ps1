<#
.SYNOPSIS
    Oilora Blue AI - verify the running application and repository state.
.DESCRIPTION
    Checks backend health + system status, frontend reachability, the SQLite
    database file, the frontend lockfile, and data directories. Prints PASS/FAIL
    per check and exits with a non-zero code if any check fails.
.EXAMPLE
    .\scripts\verify.ps1
#>
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"

$failures = 0

function Write-Check([string]$Name, [bool]$Passed, [string]$Detail) {
    if ($Passed) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] $Name - $Detail" -ForegroundColor Red
        $script:failures++
    }
}

Write-Host "Oilora Blue AI verification" -ForegroundColor Cyan

# --- Backend health ----------------------------------------------------
$BackendVersion = $null
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 5
    if ($health.success) { $BackendVersion = $health.data.version }
} catch { }
Write-Check "Backend /api/health" ($null -ne $BackendVersion) "expected success=true on port 8000"

# --- Backend system status ---------------------------------------------
$SysOk = $false
$SysDetail = "n/a"
try {
    $status = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/system/status" -TimeoutSec 5
    if ($status.success) {
        $SysOk = $true
        $SysDetail = "backend=$($status.data.backend_status) db=$($status.data.database_status) disk=$($status.data.disk_space_gb)GB"
    }
} catch { }
Write-Check "Backend /api/system/status" $SysOk $SysDetail

# --- Request ID header -------------------------------------------------
$ReqIdOk = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 5
    $ReqIdOk = [bool]$resp.Headers["X-Request-ID"]
} catch { }
Write-Check "X-Request-ID header present" $ReqIdOk "expected X-Request-ID on every response"

# --- Frontend ----------------------------------------------------------
$FrontendOk = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 10
    $FrontendOk = $resp.StatusCode -eq 200
} catch { }
Write-Check "Frontend http://localhost:3000" $FrontendOk "expected HTTP 200"

# --- Database file -----------------------------------------------------
$DbFile = Join-Path $BackendDir "oilora_blue.db"
Write-Check "SQLite database file exists" (Test-Path $DbFile) "expected $DbFile"

# --- Frontend lockfile -------------------------------------------------
$Lockfile = Join-Path $RepoRoot "frontend\package-lock.json"
Write-Check "Frontend package-lock.json exists" (Test-Path $Lockfile) "expected $Lockfile"

# --- Data directories --------------------------------------------------
$DataDir = Join-Path $RepoRoot "data"
$DataOk = (Test-Path $DataDir) -and (Test-Path (Join-Path $DataDir "uploads")) -and (Test-Path (Join-Path $DataDir "cases"))
Write-Check "Data directories exist" $DataOk "expected data\uploads and data\cases"

# --- Summary -----------------------------------------------------------
Write-Host ""
if ($failures -eq 0) {
    Write-Host "All checks passed." -ForegroundColor Green
    exit 0
} else {
    Write-Host "$failures check(s) failed." -ForegroundColor Red
    exit 1
}