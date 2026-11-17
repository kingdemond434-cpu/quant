# REGISTER MT5-AllocatorPulse -- THE ALLOCATOR'S 24/7 REACTION (2026-11-13).
#
# THE GAP. `desks/mt5/ops/box_tasks.manifest` has declared MT5-AllocatorPulse since 2026-09-23
# ("at startup + every 5 minutes (keep-alive of a 24/7 resident)", runs
# desks/mt5/research/allocator_trigger.py, lane=money) with `installer="NONE"`: the resident that
# fires `pf_allocator --mode fast` the moment MACRO_VIEW / regime_state / REGIME_ROUTER /
# sleeve_registry / gateway_state / NET_EDGE carries a real state change had no registration
# anywhere in this repository, so the principal's "24/7 and not slow" allocator ran only on the
# hourly backstop and the 5-minute MT5-AllocatorFast clock.
#
# WHAT IT REGISTERS, every value read off the manifest or the organ itself:
#   trigger    at startup, plus every 5 minutes as a keep-alive (the manifest's line). The keep-alive
#              is a no-op while the resident lives: MultipleInstances IgnoreNew absorbs it.
#   action     allocator_trigger.py --resident --interval-s 20 -- the "24/7 shape" its own
#              docstring names; 20 s is its DEFAULT_INTERVAL_S, passed explicitly so the task
#              definition says what it runs.
#   limit      none (TimeSpan zero). A resident killed by a scheduler timeout is a watcher that
#              stops watching every N hours (install_tape_tasks.ps1, the tick recorder).
#   principal  SYSTEM, ServiceAccount -- the same principal MT5-AllocatorFast (pf_allocator
#              --mode fast, Install-QuantWindows.ps1) runs under. The organ fires that same solver
#              and touches no terminal, so it needs no interactive session.
#
# WHAT IT DOES NOT DO. It sets no fraction and passes no override; allocator_trigger re-solves
# inside the heat the law already resolved and records heat_before/heat_after per firing. This
# installer only gives that organ a clock.
#
# IDEMPOTENT. Without switches it replaces any existing registration with exactly this one. With
# -IfMissing it does nothing when the task exists (the form Adopt-And-Seal.ps1's ensure-task
# loop calls; re-registering live tasks has failed with "Access is denied" on this box).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_allocator_pulse_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_allocator_pulse_task.ps1 -IfMissing
param([switch]$IfMissing, [string]$Python = 'C:\Program Files\Python314\python.exe')

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-AllocatorPulse'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Organ    = Join-Path $DeskRoot 'research\allocator_trigger.py'
$Log      = Join-Path $DeskRoot ('logs\{0}.log' -f $TaskName)
if (-not (Test-Path $Organ)) { throw "allocator_trigger.py missing at $Organ" }
if (-not (Test-Path $Python)) { throw "interpreter missing at $Python; pass -Python" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $RepoRoot -Argument (
    '/d /s /c ""{0}" -u "{1}" --resident --interval-s 20 >> "{2}" 2>&1"' -f $Python, $Organ, $Log)

# At startup, and a keep-alive every 5 minutes. The repeating shape is a -Daily trigger whose
# Repetition is copied from a -Once trigger (install_cro_cycle_tasks.ps1): a -Once repetition ends
# when its duration ends, and PowerShell 5.1's -Daily set rejects -RepetitionInterval.
$boot  = New-ScheduledTaskTrigger -AtStartup
$pulse = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date)
$pulse.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($boot, $pulse) `
    -Principal $principal -Settings $settings `
    -Description 'Allocator 24/7 reaction: allocator_trigger.py --resident fires pf_allocator --mode fast on a real state change; writes reports\ALLOCATOR_REACTION.json.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} keepalive={2} next={3} runs={4}" -f $t.TaskName, $t.State,
    $t.Triggers[1].Repetition.Interval, $i.NextRunTime, $Organ
if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
    Write-Host ("FATAL: {0} registered with no next run time" -f $TaskName)
    exit 4
}
