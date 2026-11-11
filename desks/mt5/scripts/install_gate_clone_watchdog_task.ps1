# REGISTER MT5-GateCloneWatchdog -- THE MERGE GATE'S CLONE IS HEALED BY SYSTEM (2026-11-11).
#
# Runs scripts\gate_clone_watchdog.ps1 as SYSTEM every 15 minutes, whatever adoption is doing.
# SYSTEM because C:\ProgramData\QuantBox is ACL-locked to Administrators and SYSTEM, and an
# elevated run's stale lock there is what the gate account could not remove (11-11 jam).
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists -- the form
# Adopt-And-Seal.ps1 calls on every adoption, so no person ever runs this.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_gate_clone_watchdog_task.ps1 -IfMissing
param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-GateCloneWatchdog'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'scripts\gate_clone_watchdog.ps1'
$Log      = Join-Path $DeskRoot 'logs\MT5-GateCloneWatchdog.log'
if (-not (Test-Path $Script)) { throw "gate_clone_watchdog.ps1 missing at $Script" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
    '/d /s /c powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $Script + '" ' +
    '>> "' + $Log + '" 2>&1') -WorkingDirectory $DeskRoot

# A DAILY trigger repeating every 15 minutes for one day re-arms itself at midnight and never
# expires (a -Once trigger with a long duration expired on this box on 2026-09-21).
$start = (Get-Date).Date.AddMinutes(7)
$trigger = New-ScheduledTaskTrigger -Daily -At $start
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -Priority 7

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
    'DRYRUN would register {0}: every 15 min, SYSTEM, PT10M, runs {1}' -f $TaskName, $Script
    exit 0
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Rebuilds the merge gate's jammed stateless clone (gate-repo) as SYSTEM; every 15 min." | Out-Null
$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} every 15 min runs={2}" -f $t.TaskName, $t.State, $Script
