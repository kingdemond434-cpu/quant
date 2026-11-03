<#
.SYNOPSIS
    Register the prop-fleet tasks on the trading box. Idempotent; touches only these three tasks.

.DESCRIPTION
    Runs every prop challenge account the principal registers in data\prop_accounts.json beyond the
    legacy FTMO account (whose MT5-FTMO-* tasks are unchanged):

      MT5-Prop-VenueReaders  every 5 min   prop\prop_fleet.py --role reader
      MT5-Prop-Executors     every 5 min   prop\prop_fleet.py --role executor
      MT5-Prop-Allocator     every 10 min  research\prop_challenge_allocator.py --if-due

    The allocator task covers EVERY account, the legacy one included: it re-solves an account only
    when its phase, account key, program day, balance (0.5% of initial) or universe inputs moved, or
    its report is 50 minutes old; the hourly cycle's forced solve stays as the backstop and the two
    share a run lock. Readers and executors run in the INTERACTIVE logon session of the user who
    runs the terminals over RDP (MetaTrader5 attaches only from that desktop session). Every
    account's executor is STANDBY until data\prop\<id>\EXECUTOR_ARMED exists, and its allocator
    writes CERT_BOOK_LIVE only once data\prop\<id>\ALLOCATOR_ARMED exists.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_prop_fleet_tasks.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe",
    [string] $InteractiveUser = "Administrator"
)
$ErrorActionPreference = "Stop"
$desk = Join-Path $RepoRoot "desks\mt5"
$fleet = Join-Path $desk "prop\prop_fleet.py"
$alloc = Join-Path $desk "research\prop_challenge_allocator.py"
foreach ($f in @($fleet, $alloc)) { if (-not (Test-Path $f)) { throw "missing $f" } }

$tasks = @(
    @{ Name = "MT5-Prop-VenueReaders"; Args = "`"$fleet`" --role reader"; Minutes = 5; Limit = 15
       Why = "Prop fleet venue readers: phase/state/registry for every non-legacy prop account" },
    @{ Name = "MT5-Prop-Executors"; Args = "`"$fleet`" --role executor"; Minutes = 5; Limit = 15
       Why = "Prop fleet sleeve executors, one terminal per account (standby until each EXECUTOR_ARMED)" },
    @{ Name = "MT5-Prop-Allocator"; Args = "`"$alloc`" --if-due"; Minutes = 10; Limit = 45
       Why = "Prop challenge allocator, every account, re-solved when due (standby until each ALLOCATOR_ARMED)" }
)
$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
foreach ($t in $tasks) {
    $action = New-ScheduledTaskAction -Execute $Python -Argument $t.Args -WorkingDirectory $desk
    # A DAILY trigger repeating for one day re-arms itself at midnight and never expires
    # (a -Once trigger with a long duration expired on this box on 2026-09-21).
    $trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddSeconds(40))
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddSeconds(40)) `
        -RepetitionInterval (New-TimeSpan -Minutes $t.Minutes) `
        -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes $t.Limit) `
        -MultipleInstances IgnoreNew -Priority 5
    if (Get-ScheduledTask -TaskName $t.Name -ErrorAction SilentlyContinue) {
        Set-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings | Out-Null
        Write-Host "  updated $($t.Name)"
    } else {
        Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings -Description $t.Why | Out-Null
        Write-Host "  created $($t.Name)"
    }
}
Get-ScheduledTask -TaskName "MT5-Prop-*" | Select-Object TaskName, State | Format-Table -AutoSize
