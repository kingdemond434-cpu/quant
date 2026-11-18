# REGISTER MT5-GoldHourSweep -- RE-EARN THE GOLD ENTRY HOURS, DAILY (2026-11-13).
#
# THE GAP. ops\run_gold_hour_sweep.cmd has existed since 2026-09-12, writes its own
# logs\MT5-GoldHourSweep.log, and `desks/mt5/ops/box_tasks.manifest` declared the task with
# `trigger="UNDECLARED" installer="NONE"` ("not installed on the box 2026-09-16"). So
# research\gold_hour_sweep.py -- which exists because "the sweep that chose 7/13/17 ran once and
# no organ re-runs it" -- was itself run once and by no organ.
#
# THE CADENCE IS THE RUNNER'S OWN WORDS, NOT A CHOICE MADE HERE. run_gold_hour_sweep.cmd:
# "Idempotent on the executable spec, so running it daily adds nothing once the 48 cells are in
# the docket -- it exists so a REBUILT docket never silently loses them." Daily, then.
#
# THE MINUTE IS A PLACEMENT, and it is stated as one: 03:30 box-local is clear of the :05/:12/:20
# repository-writer slots, the merge docket's :14/:44, and every other declared daily
# (ScientistTournament 02:30, ForwardReconcile 04:00, CostState 04:20, FrontierAudit 05:10).
# Nothing in the sweep depends on the hour it runs; only on running every day.
#
#   action     cmd.exe /c ops\run_gold_hour_sweep.cmd (which runs gold_hour_sweep.py --apply and
#              returns its exit code, so LastTaskResult is the sweep's own verdict).
#   principal  SYSTEM, ServiceAccount -- the same shape as MT5-FrontierAudit. The sweep only
#              appends candidate cells to the docket; it touches no terminal and no profile.
#
# IT NEVER TOUCHES THE LIVE BOOK. Every hour is emitted as a candidate cell for the same gauntlet
# as everything else (gold_hour_sweep.py's header); registering the clock arms nothing.
#
# IDEMPOTENT. Without switches it replaces any existing registration with exactly this one. With
# -IfMissing it does nothing when the task exists (the Adopt-And-Seal.ps1 ensure-task form).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_gold_hour_sweep_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_gold_hour_sweep_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-GoldHourSweep'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Runner   = Join-Path $RepoRoot 'ops\run_gold_hour_sweep.cmd'
if (-not (Test-Path $Runner)) { throw "run_gold_hour_sweep.cmd missing at $Runner" }
New-Item -ItemType Directory -Force -Path (Join-Path $DeskRoot 'logs') | Out-Null

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "{0}"' -f $Runner) `
    -WorkingDirectory $RepoRoot

# Daily at 03:30. A daily trigger re-arms itself and has no repetition duration to expire.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddHours(3).AddMinutes(30))

# StartWhenAvailable: a day missed to a reboot is caught up rather than skipped. One hour is a
# watchdog, not a budget: the sweep builds 48 rows and dedupes them against the docket.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Re-earn the gold entry hours daily: gold_hour_sweep.py --apply emits every (hour x rr) gold cell to the docket; idempotent on the executable spec.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} next={2} runs={3}" -f $t.TaskName, $t.State, $i.NextRunTime, $Runner
if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
    Write-Host ("FATAL: {0} registered with no next run time" -f $TaskName)
    exit 4
}
