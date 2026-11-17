# REGISTER MT5-RotateLogs -- THE DESK LOGS ROTATED, AND ARCHIVED WHOLE (2026-11-13).
#
# WHY. ops/rotate_logs.py existed since 2026-09-29 with no clock (hourly pass HUNT, 2026-11-13):
# MT5-Gauntlet.log had reached 1.48 GB and nothing rotated it. This gives it one daily run.
#
# WHAT IT DOES. Daily at 03:40 box-local (clear of the :05/:12/:20 repository writers, the :36
# HourlyCore start and the :50 FTMO solve), `ops\rotate_logs.py` as SYSTEM, below-normal priority.
# A log over 256 MB that no process holds open is renamed, gzip-archived WHOLE into
# desks\mt5\logs\archive\ (never overwriting, read back and SHA-256-verified before the staging
# copy is removed). Nothing is discarded. Exit 2 when a log could not be archived.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_rotate_logs_task.ps1 -IfMissing
param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-RotateLogs'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Script   = Join-Path $RepoRoot 'ops\rotate_logs.py'
$Log      = Join-Path $DeskRoot 'logs\MT5-RotateLogs.txt'
$py       = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Script)) { throw "rotate_logs.py missing at $Script" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

# Its own output goes to a .txt, not a .log, so the rotator never tries to rename the file its
# own task holds open.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
    '/d /s /c cd /d "' + $RepoRoot + '" && "' + $py + '" -u -W ignore "' + $Script + '" ' +
    '>> "' + $Log + '" 2>&1') -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddHours(3).AddMinutes(40))

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60) -Priority 7

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
    'DRYRUN would register {0}: daily 03:40, SYSTEM, PT60M, priority 7, runs {1}' -f $TaskName, $Script
    exit 0
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Rotate desk logs over 256 MB into verified gzip archives (ops\rotate_logs.py); never discards." | Out-Null
$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} next=daily 03:40 runs={2}" -f $t.TaskName, $t.State, $Script
