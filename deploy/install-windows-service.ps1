# Installs the autonomous supervisor as a Windows service that auto-starts and auto-restarts.
# Preferred method: NSSM (https://nssm.cc). Run this script from an elevated PowerShell.
#
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows-service.ps1
#
# Uninstall:  nssm remove QuantResearch confirm

$ErrorActionPreference = "Stop"
$Root   = (Resolve-Path "$PSScriptRoot\..").Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Script = Join-Path $Root "scripts\run_supervisor.py"
$Logs   = Join-Path $Root "data\logs"
$Name   = "QuantResearch"

if (-not (Test-Path $Python)) { throw "venv python not found at $Python" }
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$nssm = (Get-Command nssm -ErrorAction SilentlyContinue)
if (-not $nssm) {
  Write-Host "NSSM not found. Install it (choco install nssm) or use the Task Scheduler fallback:" -ForegroundColor Yellow
  Write-Host @"
  schtasks /Create /TN QuantResearch /SC ONSTART /RL HIGHEST /F ``
    /TR "'$Python' '$Script' --workers 3 --db data\sor_research.sqlite --lake data\lake"
  (Task Scheduler note: set 'Restart on failure' in the task's Settings tab for auto-recovery.)
"@ -ForegroundColor Cyan
  exit 1
}

Write-Host "Installing service '$Name' via NSSM..." -ForegroundColor Green
& nssm install $Name $Python $Script "--workers" "3" "--db" "data\sor_research.sqlite" "--lake" "data\lake"
& nssm set $Name AppDirectory $Root
& nssm set $Name AppStdout (Join-Path $Logs "supervisor.out.log")
& nssm set $Name AppStderr (Join-Path $Logs "supervisor.err.log")
& nssm set $Name AppRotateFiles 1
& nssm set $Name AppExit Default Restart        # auto-restart on any exit (crash recovery)
& nssm set $Name AppRestartDelay 5000
& nssm set $Name Start SERVICE_AUTO_START       # start on boot (power-loss recovery)
& nssm start $Name

Write-Host "Service '$Name' installed and started. Logs: $Logs" -ForegroundColor Green
Write-Host "Manage with:  nssm restart $Name  |  nssm stop $Name  |  Get-Service $Name"
