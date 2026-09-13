<#
.SYNOPSIS
    Register the E8 prop lane's clocks on the trading box. Idempotent; touches only E8-* tasks.

.DESCRIPTION
    THREE CLOCKS, AND THEY ARE SEPARATE ON PURPOSE.

        E8-Executor   hourly at :02   signal -> size -> send for the 20-sleeve certified book.
                                      Two minutes past the hour because the families read the
                                      LAST CLOSED bar and a pass at :00 races the close.
        E8-Book       daily at 23:40  re-selects the book against the venue's live catalogue, so
                                      an instrument E8 delists stops being traded the next day
                                      rather than becoming a rejected order every hour.
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
    param([string] $Name, [string] $Script, [string] $ScheduleArgs, [string] $Why)
    $action  = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $desk
    # RunLevel Highest so the task can write under C:\opt\quant regardless of the ACL the
    # adoption left; S4U so it runs whether or not anyone is logged in over RDP.
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
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
    -ScheduleArgs "New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours 1)" `
    -Why "signal -> size -> send for the certified E8 book (sends only while data\E8_ARMED exists)"

Set-E8Task -Name "E8-Book" -Script (Join-Path $prop "e8_book.py") `
    -ScheduleArgs "New-ScheduledTaskTrigger -Daily -At 23:40" `
    -Why "re-select the book against the venue's live catalogue"

Set-E8Task -Name "E8-Spreads" -Script (Join-Path $prop "e8_spread_sampler.py") `
    -ScheduleArgs "New-ScheduledTaskTrigger -AtStartup" `
    -Why "measure what this venue actually charges in the hours the book trades"

$armed = Join-Path $desk "data\E8_ARMED"
Write-Host ""
Write-Host ("  arming marker: {0}" -f $armed)
Write-Host ("  state now:     {0}" -f $(if (Test-Path $armed) { "ARMED -- the executor will SEND" } else { "SHADOW -- no orders" }))
Write-Host ""
Write-Host "  arm:    New-Item '$armed' -ItemType File"
Write-Host "  disarm: Remove-Item '$armed'"
