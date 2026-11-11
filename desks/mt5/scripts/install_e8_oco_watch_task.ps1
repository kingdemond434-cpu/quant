<#
.SYNOPSIS
    Register MT5-E8-OcoWatch on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    prop/e8_oco_watch.py, every minute: the gold direction lock's cancel-and-flatten pass on the
    E8 account (audit HOLD on #959, M1). It claims E8's gold fills into the shared direction state
    and cancels every resting E8 gold leg against the day's direction (and closes an E8 fill that
    landed against it) within the minute, instead of waiting for E8-Gold's five-minute pass. It
    never places an order. Armed exactly when E8-Gold is (data\E8_GOLD_ARMED); unarmed it reports
    what it would cancel (reports\E8_OCO_WATCH.json) and sends nothing.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_e8_oco_watch_task.ps1
        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_e8_oco_watch_task.ps1 -IfMissing

    -IfMissing: does nothing when the task already exists -- the form Adopt-And-Seal.ps1's ensure
    list calls on every adoption, so a box that lacks the task gains it on the next adoption.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe",
    [string] $InteractiveUser = "Administrator",
    [switch] $IfMissing
)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-E8-OcoWatch"
if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    Write-Host "  $TaskName already registered; nothing to do"
    exit 0
}
$desk   = Join-Path $RepoRoot "desks\mt5"
$script = Join-Path $desk "prop\e8_oco_watch.py"
if (-not (Test-Path $script)) { throw "e8_oco_watch.py missing at $script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $desk
# A DAILY trigger repeating every minute for one day re-arms itself at midnight and never expires
# (a -Once trigger with a long duration expired on this box on 2026-09-21).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddSeconds(20))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddSeconds(20)) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
# The same user and session as E8-Gold, so it reads the same TradeLocker credentials.
$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
# One venue login, a handful of reads and at most a few cancels: well inside the minute.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 50) `
    -MultipleInstances IgnoreNew -Priority 4

$why = "E8 gold OCO watch: cancel/flatten only, every minute; no opposite gold exposure across accounts stands past a minute"
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
