<#
.SYNOPSIS
    Register MT5-FTMO-Follower on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    prop/ftmo_follower.py, every minute, in the INTERACTIVE logon session of the user who runs the
    FTMO terminal (C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe) over RDP.
    MetaTrader5.initialize attaches to that running terminal by path, which only works from the
    same desktop session: under SYSTEM / a service / SSH it fails with -10004 No IPC connection
    while the task still looks scheduled (measured on E8-Gold, 2026-09). The lane itself refuses
    to run in session 0 or under SSH.

    STANDBY BY DEFAULT. The task runs and journals what it would send; it sends nothing until
    the principal creates the marker:

        ARM:     New-Item C:\opt\quant\desks\mt5\data\FTMO_FOLLOWER_ARMED -ItemType File
        DISARM:  Remove-Item C:\opt\quant\desks\mt5\data\FTMO_FOLLOWER_ARMED

    and the account declaration data\FTMO_LIVE_ACCOUNT.json {login, server, trade_mode,
    initial_balance} (gitignored, never committed) must match the terminal, or it does nothing.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_ftmo_follower_task.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe",
    [string] $InteractiveUser = "Administrator"
)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-FTMO-Follower"
$desk   = Join-Path $RepoRoot "desks\mt5"
$script = Join-Path $desk "prop\ftmo_follower.py"
if (-not (Test-Path $script)) { throw "ftmo_follower.py missing at $script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $desk
# A DAILY trigger repeating every minute for one day re-arms itself at midnight and never expires
# (a -Once trigger with a long duration expired on this box on 2026-09-21).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddSeconds(30))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddSeconds(30)) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
# One pass takes seconds; a 50-second watchdog keeps a wedged pass from stacking on the next one.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 50) `
    -MultipleInstances IgnoreNew -Priority 4

$why = "FTMO follower: one gold_asia order in E8's filled direction (standby unless data\FTMO_FOLLOWER_ARMED)"
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
