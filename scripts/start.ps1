<#
.SYNOPSIS
    Oilora Blue AI - start the backend and frontend development servers.
.DESCRIPTION
    Starts the FastAPI backend on 127.0.0.1:8000 and the Next.js frontend on
    localhost:3000 as detached processes, writes their PIDs to .freebuff\pids,
    and waits until both answer. Run .\scripts\stop.ps1 to stop them.
.PARAMETER BackendPort
    Port for the FastAPI backend (default 8000).
.PARAMETER FrontendPort
    Port for the Next.js frontend (default 3000).
.EXAMPLE
    .\scripts\start.ps1
#>
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$LogDir = Join-Path $RepoRoot ".freebuff\logs"
$PidDir = Join-Path $RepoRoot ".freebuff\pids"
New-Item -ItemType Directory -Force -Path $LogDir, $PidDir | Out-Null

function Test-PortInUse([int]$Port) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
        return $conn.Count -gt 0
    } catch {
        return $false
    }
}

# --- Port checks -------------------------------------------------------
if (Test-PortInUse $BackendPort) {
    Write-Error "Backend port $BackendPort is already in use. Run .\scripts\stop.ps1 first (or pick another port with -BackendPort)."
}
if (Test-PortInUse $FrontendPort) {
    Write-Error "Frontend port $FrontendPort is already in use. Run .\scripts\stop.ps1 first (or pick another port with -FrontendPort)."
}

# --- Backend -----------------------------------------------------------
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$BackendPy = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$BackendLog = Join-Path $LogDir "backend.log"
$BackendErr = Join-Path $LogDir "backend.log.err"
$BackendPidFile = Join-Path $PidDir "backend.pid"

Write-Host "Starting backend on http://127.0.0.1:$BackendPort ..." -ForegroundColor Cyan
$BackendProc = Start-Process -FilePath $BackendPy `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendErr `
    -WindowStyle Hidden `
    -PassThru
$BackendProc.Id | Out-File -FilePath $BackendPidFile -Encoding ascii

$BackendUp = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    if ($BackendProc.HasExited) {
        Write-Error "Backend exited during startup (exit $($BackendProc.ExitCode)). See $BackendErr"
    }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health" -TimeoutSec 2
        if ($health.success) { $BackendUp = $true; break }
    } catch { }
}
if (-not $BackendUp) {
    Write-Error "Backend did not answer /api/health on port $BackendPort. See $BackendLog and $BackendErr"
}
Write-Host "  [OK] backend healthy (pid $($BackendProc.Id))" -ForegroundColor Green

# --- Frontend ----------------------------------------------------------
$FrontendLog = Join-Path $LogDir "frontend.log"
$FrontendErr = Join-Path $LogDir "frontend.log.err"
$FrontendPidFile = Join-Path $PidDir "frontend.pid"

Write-Host "Starting frontend on http://localhost:$FrontendPort ..." -ForegroundColor Cyan
$FrontendProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "-p", "$FrontendPort") `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError $FrontendErr `
    -WindowStyle Hidden `
    -PassThru
$FrontendProc.Id | Out-File -FilePath $FrontendPidFile -Encoding ascii

$FrontendUp = $false
for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Milliseconds 500
    if ($FrontendProc.HasExited) {
        Write-Error "Frontend exited during startup. See $FrontendErr"
    }
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $FrontendUp = $true; break }
    } catch { }
}
if (-not $FrontendUp) {
    Write-Error "Frontend did not answer on port $FrontendPort. See $FrontendLog and $FrontendErr"
}
Write-Host "  [OK] frontend responding (pid $($FrontendProc.Id))" -ForegroundColor Green

# --- Summary -----------------------------------------------------------
Write-Host ""
Write-Host "Oilora Blue AI is running:" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:$FrontendPort  (pid $($FrontendProc.Id))"
Write-Host "  Backend  : http://127.0.0.1:$BackendPort   (pid $($BackendProc.Id))"
Write-Host "  API docs : http://127.0.0.1:$BackendPort/api/docs"
Write-Host ""
Write-Host "Note: these detached processes do not survive a machine restart."
Write-Host "Stop them anytime with .\scripts\stop.ps1"