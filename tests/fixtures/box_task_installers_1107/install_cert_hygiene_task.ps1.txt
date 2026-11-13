# REGISTER MT5-CertHygiene -- EVICT CERTIFICATES THAT CAN NEVER BE ENROLLED, DAILY (2026-11-13).
#
# THE GAP. ops\organ_contract.py has named MT5-CertHygiene since 2026-09-12 as the clock that
# owns desks\mt5\reports\CERTIFICATE_HYGIENE.json, with a max age of 1560 minutes, and
# `desks/mt5/ops/box_tasks.manifest` declared it `trigger="UNDECLARED" runs="UNKNOWN"
# installer="NONE"` ("not installed on the box 2026-09-16"). The contract therefore judged a
# clock that did not exist under that name.
#
# WHERE EVERY VALUE COMES FROM:
#   runs       desks\mt5\research\certificate_hygiene.py --apply -- the only producer of
#              CERTIFICATE_HYGIENE.json in this repository, in the mode that moves the unrunnable
#              rows out (it is invoked exactly so as the first organ of run_frontier_audit.cmd).
#   cadence    DAILY: the contract's 1560-minute max age is the desk's daily allowance (26 h,
#              the same figure MT5-ForwardReconcile's daily contract carries).
#   minute     03:50 box-local is a PLACEMENT, stated as one: ten minutes before
#              MT5-ForwardReconcile (daily 04:00), because certificate_hygiene's own header says
#              every unrunnable row surfaces "as an ENROL-GAP line on every forward reconcile",
#              so the reconcile should read the registry hygiene leaves behind. It is also clear of
#              the :05/:12/:20 writer slots and finishes long before MT5-FrontierAudit (05:10)
#              re-runs the same idempotent pass.
#   principal  SYSTEM, ServiceAccount -- the same shape as MT5-FrontierAudit, which already runs
#              this organ under SYSTEM.
#
# IT NEVER GUESSES PARAMETERS AND NEVER DELETES. A row is MOVED to its own file with its evidence
# kept (certificate_hygiene.py's header). A second pass the same day finds nothing to move.
#
# IDEMPOTENT. Without switches it replaces any existing registration with exactly this one. With
# -IfMissing it does nothing when the task exists (the Adopt-And-Seal.ps1 ensure-task form).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_cert_hygiene_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_cert_hygiene_task.ps1 -IfMissing
param([switch]$IfMissing, [string]$Python = 'C:\Program Files\Python314\python.exe')

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-CertHygiene'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Organ    = Join-Path $DeskRoot 'research\certificate_hygiene.py'
$Log      = Join-Path $DeskRoot ('logs\{0}.log' -f $TaskName)
if (-not (Test-Path $Organ)) { throw "certificate_hygiene.py missing at $Organ" }
if (-not (Test-Path $Python)) { throw "interpreter missing at $Python; pass -Python" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $RepoRoot -Argument (
    '/d /s /c ""{0}" -u "{1}" --apply >> "{2}" 2>&1"' -f $Python, $Organ, $Log)

# Daily at 03:50. A daily trigger re-arms itself and has no repetition duration to expire.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddHours(3).AddMinutes(50))

# StartWhenAvailable: a day missed to a reboot is caught up rather than skipped. Thirty minutes
# is a watchdog, not a budget: the pass reads one registry and moves a handful of rows.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Certificate hygiene, daily before the forward reconcile: certificate_hygiene.py --apply moves never-enrollable certificates out with their evidence kept; writes reports\CERTIFICATE_HYGIENE.json.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} next={2} runs={3}" -f $t.TaskName, $t.State, $i.NextRunTime, $Organ
if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
    Write-Host ("FATAL: {0} registered with no next run time" -f $TaskName)
    exit 4
}
