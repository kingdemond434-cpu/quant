<#
.SYNOPSIS
    Register MT5-DeepForestRegions on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    research\deep_forest_regions.py every hour (zuck 2026-11-25 17:48Z: the deep forest runs on
    the box, at least as good as the cloud pass). One pass works the regions round a saved cursor
    (Asia first; the 20 always-zero regions first in any pass that opens a 6-hour UTC window), up
    to 4 regions at once with the cloud's exact miner command line, and publishes
    desks\mt5\reports\DEEP_FOREST_REGIONS.json. SYSTEM, BELOW_NORMAL (research class: Priority 7),
    one instance at a time, 58-minute limit.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_deep_forest_regions_task.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe"
)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-DeepForestRegions"
$desk   = Join-Path $RepoRoot "desks\mt5"
$script = Join-Path $desk "research\deep_forest_regions.py"
if (-not (Test-Path $script)) { throw "deep_forest_regions.py missing at $script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $desk
# A DAILY trigger repeating every hour for one day re-arms itself at midnight and never expires.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(2))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(2)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 58) `
    -MultipleInstances IgnoreNew -Priority 7

$why = "Deep forest miner, every region on the box (cloud parity); DEEP_FOREST_REGIONS.json"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings | Out-Null
    Write-Host "  updated $TaskName"
} else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $why | Out-Null
    Write-Host "  created $TaskName"
}
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table -AutoSize
