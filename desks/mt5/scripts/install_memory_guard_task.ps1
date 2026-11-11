# MT5-MEMORYGUARD: A RESEARCH JOB MAY NEVER STARVE THE LIVE TERMINALS (2026-11-11).
#
# The FrontierAudit organ libs.ops.scaling_laws grew to more than 30 GB of commit on this 96 GB
# box and nothing could stop it: every desk session is non-elevated and cannot end another user's
# process. This registers ops/memory_guard.py as a SYSTEM task every two minutes. It only ever
# acts on research python (never a terminal, never the money path, never a non-python process):
# a single research process over a quarter of physical memory, or the largest one when the box
# is under pressure, is stopped and re-queued; when headroom returns it is run again inside a
# memory-capped job object, at most twice a day. A healthy box is a report and nothing else.
# See the module docstring for the rules.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task exists -- the form Adopt-And-Seal.ps1
# calls on every adoption, so the box gains the guard on the first adoption after it ships.
#
# NO cmd.exe AND NO `>>` REDIRECT: python is the task's own action, so there is no inherited log
# handle for an orphan to hold (the held-log signature MergeDocket and CacheWarm show). The
# record is desks\mt5\reports\MEMORY_GUARD.json, written every pass.

param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'
$TaskName = 'MT5-MemoryGuard'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$py = 'C:\Program Files\Python314\python.exe'
$guard = Join-Path $RepoRoot 'ops\memory_guard.py'
if (-not (Test-Path $guard)) { throw "memory_guard.py missing at $guard" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute $py -WorkingDirectory $RepoRoot `
            -Argument ('-u "' + $guard + '" --apply')
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
             -RepetitionInterval (New-TimeSpan -Minutes 2)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable -Priority 4
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
    'DRYRUN would register {0} every 2m as SYSTEM, PT5M limit, priority 4' -f $TaskName
    exit 0
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Description 'Stops and re-queues a runaway research python job before it starves the MT5 terminals; never touches the money path.' -Force | Out-Null
$t = Get-ScheduledTask -TaskName $TaskName
'{0} registered: {1}' -f $TaskName, $t.State
