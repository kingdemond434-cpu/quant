<#
.SYNOPSIS
    Register the E8 prop lane's clocks on the trading box. Idempotent; touches only E8-* tasks.

.DESCRIPTION
    THREE ACTIVE CLOCKS, AND THEY ARE SEPARATE ON PURPOSE.

        E8-Executor   every 5 min     guard, flatten and manage positions inherited from the
                                      retired certificate-selected FX book; opens no new FX.
        E8-Gold       every 5 min     the same three gold windows as the Fusion book.
        E8-Spreads    at boot         the cost sampler. It is the only measurement of what this
                                      venue actually charges during the hours the book trades,
                                      and every pass-probability number depends on it.

    ARMING IS A FILE, NOT A FLAG IN A TASK. `data/E8_ARMED` present means the executor sends;
    absent means it does everything else and writes the same ledger. That is deliberate: the
    kill switch has to be something a person can operate in one action, from a file browser, at
    three in the morning, without editing a scheduled task or knowing PowerShell. The MT5
    gateway's GENERIC_EXEC_ENABLED works the same way for the same reason.

        ARM:     New-Item C:\opt\quant\desks\mt5\data\E8_ARMED -ItemType File
        DISARM:  Remove-Item C:\opt\quant\desks\mt5\data\E8_ARMED

    Disarming does not close anything. Open positions keep their stops -- every order this lane
    sends carries one at the venue -- and the guard still flattens on a stand-down or a breach on
    the next pass, because those run regardless of arming.
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe"
)
$ErrorActionPreference = "Stop"

$prop = Join-Path $RepoRoot "desks\mt5\prop"
$desk = Join-Path $RepoRoot "desks\mt5"

function Set-E8Task {
    param([string] $Name, [string] $Script, [string] $ScheduleArgs, [string] $Why,
          [string] $ExtraArgs = "")
    $arguments = "`"$Script`""
    if ($ExtraArgs) { $arguments += " $ExtraArgs" }
    $action  = New-ScheduledTaskAction -Execute $Python -Argument $arguments -WorkingDirectory $desk
    # RunLevel Highest so the task can write under C:\opt\quant regardless of the ACL the
    # adoption left; S4U so it runs whether or not anyone is logged in over RDP.
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    # AN EXECUTION LIMIT SHORTER THAN THE WORK IS NOT A SAFETY RAIL, IT IS A GUARANTEED KILL.
    # Measured 2026-09-13 on MT5-Daily, registered the same day with a 3-hour cap: daily_cycle's
    # own leg budgets sum past that before the network miners are counted, so the run was
    # terminated mid-flight having produced real output all the way to the cut, never wrote its
    # state file, and left 68 artifacts frozen at 49h looking like a dead organ. These E8 tasks
    # are minutes of work, so 50 minutes is generous here -- but the lesson is that the limit must
    # be read off the job's own budgets and not chosen for being a round number.
    $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 50) `
                    -MultipleInstances IgnoreNew
    $trigger = Invoke-Expression $ScheduleArgs
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Set-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings | Out-Null
        Write-Host ("  updated {0,-14} {1}" -f $Name, $Why)
    } else {
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings -Description $Why | Out-Null
        Write-Host ("  created {0,-14} {1}" -f $Name, $Why)
    }
}

Write-Host "E8 PROP LANE"
Set-E8Task -Name "E8-Executor" -Script (Join-Path $prop "e8_executor.py") `
    -ExtraArgs "--manage-only" `
    -ScheduleArgs "New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)" `
    -Why "manage/flatten inherited E8 positions; legacy FX entry is retired"

Set-E8Task -Name "E8-Gold" -Script (Join-Path $prop "e8_gold.py") `
    -ScheduleArgs "New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)" `
    -Why "mirror the three Fusion gold windows (sends only while data\E8_GOLD_ARMED exists)"

# Historical task retained as an auditable object, but disabled: regenerating a retired FX book
# is activity with no consumer and previously caused unintended FX exposure.
if (Get-ScheduledTask -TaskName "E8-Book" -ErrorAction SilentlyContinue) {
    Disable-ScheduledTask -TaskName "E8-Book" | Out-Null
    Write-Host "  disabled E8-Book        retired certificate-selected FX lane"
}

Set-E8Task -Name "E8-Spreads" -Script (Join-Path $prop "e8_spread_sampler.py") `
    -ScheduleArgs "New-ScheduledTaskTrigger -AtStartup" `
    -Why "measure what this venue actually charges in the hours the book trades"

$armed = Join-Path $desk "data\E8_ARMED"
$goldArmed = Join-Path $desk "data\E8_GOLD_ARMED"
Write-Host ""
Write-Host ("  arming marker: {0}" -f $armed)
Write-Host ("  state now:     {0}" -f $(if (Test-Path $armed) { "ARMED -- the executor will SEND" } else { "SHADOW -- no orders" }))
Write-Host ("  gold state:    {0}" -f $(if (Test-Path $goldArmed) { "ARMED -- E8-Gold will SEND" } else { "SHADOW -- no gold orders" }))
Write-Host ""
Write-Host "  arm:    New-Item '$armed' -ItemType File"
Write-Host "  disarm: Remove-Item '$armed'"
