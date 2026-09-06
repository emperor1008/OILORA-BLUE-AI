<#
.SYNOPSIS
    Oilora Blue AI - stop the development servers started by start.ps1.
.DESCRIPTION
    Stops processes recorded in .freebuff\pids (created by start.ps1) and any
    stray node/python processes whose command line references this repository.
    It never stops unrelated processes. PID files are removed afterwards.
.EXAMPLE
    .\scripts\stop.ps1
#>
$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$PidDir = Join-Path $RepoRoot ".freebuff\pids"

$stopped = 0

function Stop-Tree([int]$TargetPid, [string]$Label) {
    try {
        taskkill /PID $TargetPid /T /F 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] stopped $Label (pid $TargetPid)" -ForegroundColor Green
            $script:stopped++
        }
    } catch { }
}

# --- Stop by recorded PID files ----------------------------------------
if (Test-Path $PidDir) {
    Get-ChildItem $PidDir -Filter "*.pid" | ForEach-Object {
        $pidValue = (Get-Content $_.FullName | Select-Object -First 1).Trim()
        if ($pidValue -match "^\d+$") {
            Stop-Tree ([int]$pidValue) "$($_.BaseName)"
        }
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "No PID files found at $PidDir" -ForegroundColor Yellow
}

# --- Fallback: stray Oilora Blue AI processes --------------------------
# A process is treated as ours only when its command line both (a) looks like
# a Next.js dev server or this app's uvicorn and (b) references this repository
# or the project's backend port. Unrelated node/python processes are untouched.
$stray = Get-CimInstance Win32_Process -Filter "Name='node.exe' or Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        ($_.CommandLine -match "\bnext\b|uvicorn|app\.main:app") -and
        ($_.CommandLine.Contains($RepoRoot) -or $_.CommandLine -match "--port\s+8000")
    }

foreach ($p in $stray) {
    Stop-Tree ([int]$p.ProcessId) "stray $($p.Name)"
}

if ($stopped -eq 0) {
    Write-Host "No Oilora Blue AI processes were running." -ForegroundColor Yellow
} else {
    Write-Host "Stopped $stopped process tree(s)." -ForegroundColor Green
}