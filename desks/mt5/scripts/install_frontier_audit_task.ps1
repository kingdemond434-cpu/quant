# REGISTER MT5-FrontierAudit -- THE DAILY FRONTIER MEASUREMENT LANE (2026-09-30).
#
# THE GAP. `desks/mt5/ops/box_tasks.manifest` declared MT5-FrontierAudit (daily 05:10, runs
# ops/run_frontier_audit.cmd) with `installer="NONE"`: thirty organs whose only schedule lived in
# one machine's task registry. A rebuilt box would never run them again and nothing would say so.
#
# WHAT IT DOES. Registers MT5-FrontierAudit -- daily at 05:10 box-local, clear of the :05/:12/:20
# repository-writer slots -- as `cmd.exe /c ops\run_frontier_audit.cmd`, SYSTEM, the same
# principal shape as MT5-AdoptRelease. The runner now exits 1 when any organ fails (it used to
# end `exit /b 0`), so LastTaskResult is a real verdict.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists -- that is the form
# Adopt-And-Seal.ps1 calls on every adoption, so a box that lacks the task gains it within the
# hour of adopting this commit and a box that has it is never re-registered (re-registering live
# S4U tasks has failed with "Access is denied" on this box). Without -IfMissing it replaces the
# registration with exactly this one, which is the same end state however often it runs.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_frontier_audit_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_frontier_audit_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-FrontierAudit'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Runner   = Join-Path $RepoRoot 'ops\run_frontier_audit.cmd'
if (-not (Test-Path $Runner)) { throw "run_frontier_audit.cmd missing at $Runner" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "{0}"' -f $Runner) `
    -WorkingDirectory $RepoRoot

# Daily at 05:10 (the cadence box_tasks.manifest declares). A daily trigger re-arms itself and
# has no repetition duration to expire (see install_adopt_release_task.ps1, 2026-09-22).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddHours(5).AddMinutes(10))

# StartWhenAvailable: a 05:10 missed to a reboot is caught up rather than skipped a whole day.
# FOUR HOURS is a watchdog, not a budget: thirty organs, two adversary generations and the bench
# run in sequence, and a limit below the slowest honest pass only ever kills honest passes.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Frontier measurement lane: thirty read-only organs, daily; exits 1 when any organ failed." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} next=daily 05:10 runs={2}" -f $t.TaskName, $t.State, $Runner
