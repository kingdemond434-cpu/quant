# REGISTER MT5-PORTFOLIOCONTROLLER ON ITS OWN, AND RUN IT NOW (2026-10-13).
#
# The 24/7 portfolio controller (research/portfolio_controller.py, phase 1: the online edge
# monitor) re-reads the live ledger and forward clocks and republishes reports/EDGE_MONITOR.json
# every FIVE minutes, so a sleeve's posterior moves within minutes of a fill rather than at the
# next hourly pass. The hourly cycle runs the same module as a leg ahead of pf_allocator; that
# leg is the floor if this task is absent. It reads files and writes reports; it never places,
# sizes or closes an order.
#
# Trigger shape and principal handling are install_stall_watch_task.ps1's, for its reasons: a
# DAILY trigger repeating every five minutes for one day (a long -Once repetition has expired on
# this box), offset to :01; an existing task's principal is kept unchanged.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_portfolio_controller_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-PortfolioController'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'research\portfolio_controller.py'
if (-not (Test-Path $Script)) { throw "portfolio_controller.py missing at $Script" }
$LogDir   = Join-Path $DeskRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log      = Join-Path $LogDir 'MT5-PortfolioController.log'

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $DeskRoot -Argument `
    ("/d /s /c `"py -3 `"{0}`" >> `"{1}`" 2>&1`"" -f $Script, $Log)

$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(1))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(1)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    $principal = New-ScheduledTaskPrincipal -UserId $existing.Principal.UserId `
        -LogonType $existing.Principal.LogonType -RunLevel Highest
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
} else {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Every 5 minutes: portfolio controller phase 1 (edge posteriors, decay alarm, posterior fraction) -> reports\EDGE_MONITOR.json; never touches an order." | Out-Null

Start-ScheduledTask -TaskName $TaskName
"installed and started $TaskName; artifact: desks\mt5\reports\EDGE_MONITOR.json; log: $Log"
