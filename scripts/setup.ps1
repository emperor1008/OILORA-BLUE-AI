<#
.SYNOPSIS
    Oilora Blue AI — one-time setup for the local development environment.
.DESCRIPTION
    Checks prerequisites, creates backend\.venv, installs backend core + dev
    dependencies, and installs frontend dependencies (npm ci with the lockfile).
    Never modifies files outside the repository and never deletes user files.
.EXAMPLE
    .\scripts\setup.ps1
#>
$ErrorActionPreference = "Stop"

# ─── Locate repository root ────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

Write-Host "Oilora Blue AI setup" -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"

# ─── Prerequisites ─────────────────────────────────────────────────────
$PythonOk = $false
try {
    $PyVersion = python --version 2>&1
    if ($PyVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
            $PythonOk = $true
        }
    }
} catch { }
if (-not $PythonOk) {
    Write-Error "Python 3.10+ is required but was not found on PATH. Install it and retry."
}
Write-Host "  [OK] $PyVersion"

$NodeOk = $false
try {
    $NodeVersion = node --version 2>&1
    if ($NodeVersion -match "v(\d+)") {
        if ([int]$Matches[1] -ge 18) { $NodeOk = $true }
    }
} catch { }
if (-not $NodeOk) {
    Write-Error "Node.js 18+ is required but was not found on PATH. Install it and retry."
}
Write-Host "  [OK] Node $NodeVersion"

try {
    $null = npm --version 2>&1
} catch {
    Write-Error "npm was not found on PATH."
}
Write-Host "  [OK] npm present"

# ─── Backend virtual environment ───────────────────────────────────────
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend virtual environment..." -ForegroundColor Yellow
    Push-Location $BackendDir
    try {
        python -m venv ".venv"
        if (-not (Test-Path $VenvPython)) {
            Write-Error "Failed to create the virtual environment at backend\.venv"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  [OK] backend\.venv already exists"
}

Write-Host "Installing backend dependencies (core + dev)..." -ForegroundColor Yellow
& $VenvPython -m pip install --quiet --disable-pip-version-check `
    -r (Join-Path $BackendDir "requirements.txt") `
    -r (Join-Path $BackendDir "requirements-dev.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Backend dependency installation failed (pip exit $LASTEXITCODE)."
}
Write-Host "  [OK] backend dependencies installed"

# ─── Frontend dependencies ─────────────────────────────────────────────
Push-Location $FrontendDir
try {
    if (Test-Path "package-lock.json") {
        Write-Host "Installing frontend dependencies (npm ci)..." -ForegroundColor Yellow
        npm ci --no-audit --no-fund
    } else {
        Write-Host "No package-lock.json found; running npm install..." -ForegroundColor Yellow
        npm install --no-audit --no-fund
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Frontend dependency installation failed (npm exit $LASTEXITCODE)."
    }
} finally {
    Pop-Location
}
Write-Host "  [OK] frontend dependencies installed"

# ─── Summary ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. .\scripts\start.ps1     # start backend + frontend"
Write-Host "  2. .\scripts\verify.ps1     # confirm both are healthy"
Write-Host "  3. Open http://localhost:3000 in your browser"