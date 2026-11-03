<#
.SYNOPSIS
    Register MT5-FTMO-Executor on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    prop/ftmo_executor.py, every five minutes, in the INTERACTIVE logon session of the user who
    runs the FTMO terminal over RDP (MetaTrader5 attaches to a running terminal only from that
    desktop session; the executor refuses session 0 and SSH). It trades every non-gold sleeve the
    FTMO allocator lays into CERT_BOOK_LIVE's ftmo block, behind FTMO's loss rails and the
    cross-account opposite-side fence. STANDBY until data\FTMO_EXECUTOR_ARMED exists: until then
    it logs what it would send (reports\FTMO_EXEC.json, data\ftmo_exec_intents.jsonl); once the
    marker exists it SENDS real orders to the FTMO account.

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_ftmo_executor_task.ps1
#>
[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe",
    [string] $InteractiveUser = "Administrator"
)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-FTMO-Executor"
$desk   = Join-Path $RepoRoot "desks\mt5"
$script = Join-Path $desk "prop\ftmo_executor.py"
if (-not (Test-Path $script)) { throw "ftmo_executor.py missing at $script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$script`"" -WorkingDirectory $desk
# A DAILY trigger repeating every five minutes for one day re-arms itself at midnight and never expires
# (a -Once trigger with a long duration expired on this box on 2026-09-21).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddSeconds(30))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddSeconds(30)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest
# A pass reads ~900 H1 bars per funded sleeve and sends at most one order each: four minutes.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -MultipleInstances IgnoreNew -Priority 4

$why = "FTMO sleeve executor: the FTMO allocator's non-gold sleeves, signal -> size -> send (standby until FTMO_EXECUTOR_ARMED)"
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
