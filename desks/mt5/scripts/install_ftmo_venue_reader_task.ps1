<#
.SYNOPSIS
    Register MT5-FTMO-VenueReader on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    prop/ftmo_venue_reader.py, every five minutes, in the INTERACTIVE logon session of the user who
    runs the FTMO terminal over RDP (MetaTrader5 attaches to a running terminal only from that
    desktop session; the reader refuses session 0 and SSH). READ-ONLY: it sends no order. It
    publishes reports\FTMO_ACCOUNT_STATE.json (phase, balance, equity, day-start balance, trading
    days), data\ftmo_registry.json and, once a day, data\cost_surface_ftmo.json for
    research\prop_challenge_allocator.py.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_ftmo_venue_reader_task.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe",
    [string] $InteractiveUser = "Administrator"
)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-FTMO-VenueReader"
$desk   = Join-Path $RepoRoot "desks\mt5"
$script = Join-Path $desk "prop\ftmo_venue_reader.py"
if (-not (Test-Path $script)) { throw "ftmo_venue_reader.py missing at $script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $desk
# A DAILY trigger repeating every five minutes for one day re-arms itself at midnight and never expires
# (a -Once trigger with a long duration expired on this box on 2026-09-21).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddSeconds(30))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddSeconds(30)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
# A pass takes seconds; the daily surface rebuild pulls ~60 symbols of H1 bars, so four minutes.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew -Priority 4

$why = "FTMO venue reader: account phase/state, symbol list and FTMO hour spreads for the FTMO allocator (read-only)"
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
