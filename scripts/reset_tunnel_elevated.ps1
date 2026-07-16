# Elevated full reset of the desk processes + tunnel. Clears session-0 zombies that a normal
# window can't kill, then rebuilds one clean set via the watchdog. Run ELEVATED:
#   Start-Process powershell -Verb RunAs -ArgumentList '-ExecutionPolicy','Bypass','-File','C:\Users\dell\quant-platform\scripts\reset_tunnel_elevated.ps1'
$ErrorActionPreference = "Continue"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { Write-Host "NOT ELEVATED -- relaunch via the Start-Process ... -Verb RunAs command." -ForegroundColor Red; Read-Host "Enter to close"; exit 1 }

Set-Location C:\Users\dell\quant-platform
Write-Host "[1/4] killing ALL pythonw + python + ngrok (session 0 + 1)..." -ForegroundColor Yellow
Get-Process pythonw, python, ngrok -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 4
Remove-Item data\tunnel_heartbeat, data\cashcarry_exec_heartbeat, data\liquidation_heartbeat -ErrorAction SilentlyContinue
Start-Sleep 2
$left = @(Get-Process pythonw -ErrorAction SilentlyContinue).Count
Write-Host ("      pythonw remaining: {0} (should be 0)" -f $left) -ForegroundColor Cyan

Write-Host "[2/4] rebuilding one clean set via watchdog..." -ForegroundColor Yellow
& .venv\Scripts\python.exe scripts\watchdog.py
Start-Sleep 24

Write-Host "[3/4] verifying..." -ForegroundColor Yellow
$ng = @(Get-Process ngrok -ErrorAction SilentlyContinue).Count
$exec = Test-Path data\cashcarry_exec_heartbeat
Write-Host ("      ngrok agents: {0} | executor: {1}" -f $ng, $(if($exec){'up'}else{'DOWN'})) -ForegroundColor Cyan
try {
  $s = (Invoke-WebRequest 'https://brunette-pound-skiing.ngrok-free.dev/' -UseBasicParsing -TimeoutSec 12 -Headers @{'ngrok-skip-browser-warning'='1'}).StatusCode
  Write-Host ("[4/4] PUBLIC URL -> HTTP {0}  (tunnel is LIVE)" -f $s) -ForegroundColor Green
} catch {
  Write-Host ("[4/4] public URL still: {0} -- wait 30s and refresh your phone once" -f $_.Exception.Message) -ForegroundColor Yellow
}
Write-Host "https://brunette-pound-skiing.ngrok-free.dev" -ForegroundColor Green
Read-Host "Done. Press Enter to close"
