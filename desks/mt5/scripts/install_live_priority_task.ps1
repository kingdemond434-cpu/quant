<#
.SYNOPSIS
    Register MT5-LivePriority on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    scripts/live_priority.py, every minute, in the INTERACTIVE logon session that runs the MT5
    terminals (the same principal as the FTMO tasks, RunLevel Highest, so it may open the
    terminals and the live executors). It RAISES every live process (terminal64.exe, the gateway,
    the E8 and FTMO executors and their children) to ABOVE_NORMAL, never past it, never lowers
    anything and never touches a non-live process. Report: desks\mt5\reports\LIVE_PRIORITY.json.
    Revert without a push: desks\mt5\data\LIVE_PRIORITY.json = {"enabled": false}.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_live_priority_task.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\pythonw.exe",  # no console flash every minute
    [string] $InteractiveUser = "Administrator"
)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-LivePriority"
$desk   = Join-Path $RepoRoot "desks\mt5"
$script = Join-Path $desk "scripts\live_priority.py"
if (-not (Test-Path $script)) { throw "live_priority.py missing at $script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $desk
# A DAILY trigger repeating every minute for one day re-arms itself at midnight and never expires
# (a -Once trigger with a long duration expired on this box on 2026-09-21).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddSeconds(15))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddSeconds(15)) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew -Priority 4

$why = "Live priority keeper: MT5 terminals and live executors at ABOVE_NORMAL (raise only)"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings | Out-Null
    Write-Host "  updated $TaskName"
} else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $why | Out-Null
    Write-Host "  created $TaskName"
}
Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table -AutoSize
