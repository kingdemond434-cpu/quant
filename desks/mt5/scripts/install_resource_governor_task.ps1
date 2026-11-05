# THE RESOURCE GOVERNOR MUST RUN AS SYSTEM, OR IT SEES NOTHING (measured 2026-11-05 22:54Z).
#
# Desk health dry-ran ops/resource_governor.py from an unelevated token. 274 processes in the
# SYSTEM and elevated task trees (departments, forests, Hourly, MergeDocket, miners) were
# UNREADABLE, so the judge-core hold (rule 4) had almost nothing to bind to: about 11 of the 13
# busy cores went to processes nobody could read, and the judge sat at 1.96 cores. A SYSTEM
# token reads every command line, which is what the governor's classes are built on.
#
# WHAT IT DOES. Registers Quant-ResourceGovernor as SYSTEM, one tick every minute, PT5M limit,
# IgnoreNew. Task priority 5 (NORMAL class): it is a control, so it must still get CPU when
# research fills the box, and it never outranks the live E8 clocks. The governor itself only
# raises CRITICAL trees to NORMAL and holds research off the judge's 8 cores; it never lowers,
# kills or suspends anything.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists. That is the form
# Adopt-And-Seal's ensure-task list runs, so a missing task appears on the first adoption after
# this ships and a live one is never touched. -DryRun says what it would register.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_resource_governor_task.ps1 -IfMissing

param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'
$TaskName = 'Quant-ResourceGovernor'
$py = 'C:\Program Files\Python314\python.exe'

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
  Write-Output "$TaskName already registered; -IfMissing leaves it alone"
  exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"' + $py + '" -u ops\resource_governor.py --once ' +
  '>> C:\opt\quant\desks\mt5\logs\Quant-ResourceGovernor.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
             -RepetitionInterval (New-TimeSpan -Minutes 1)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable `
              -Priority 5

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
  Write-Output "DRYRUN would register $TaskName as SYSTEM every 1m, PT5M limit, priority 5"
  exit 0
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null
$t = Get-ScheduledTask -TaskName $TaskName
Write-Output ("$TaskName registered: " + $t.State + ' priority=' + $t.Settings.Priority +
              ' user=' + $t.Principal.UserId)
