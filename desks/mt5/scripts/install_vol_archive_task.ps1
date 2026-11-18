# REGISTER MT5-VolArchive ALONE -- THE IMPLIED-VOL ARCHIVE, HOURLY AT :40 (2026-11-13).
#
# THE GAP. `desks/mt5/ops/box_tasks.manifest` declared MT5-VolArchive `trigger="UNDECLARED"
# installer="NONE"` -- while desks\mt5\recorders\install_tape_tasks.ps1 has registered it all
# along ("MT5-VolArchive HOURLY, at :40"). The manifest was wrong about the cadence and about the
# installer. But that installer cannot be re-run just to restore the vol archive: it also
# unregisters, re-registers and STARTS MT5-TickRecorder, the 24/7 resident whose every lost
# second is quotes no vendor sells. So a box that lacks only MT5-VolArchive needed a way to get it
# back that touches nothing else. This is that way.
#
# EVERY VALUE IS install_tape_tasks.ps1's OWN, so the two can never disagree about the task
# (tests/scripts/test_box_task_installers.py pins the module and the minute in both):
#   action     <Python> -3 -m recorders.vol_archive, working directory desks\mt5.
#   trigger    hourly at :40 -- "second priority behind the tape and deliberately so ... hourly
#              rather than daily because the public series restate intraday and the vintage IS
#              the asset" (install_tape_tasks.ps1's header).
#   settings   IgnoreNew, StartWhenAvailable, a 50-minute limit (Install-DeskTask's non-resident
#              settings).
#   principal  -RunAs (default: the account running this installer), LogonType S4U: headless and
#              survives logoff (install_cro_cycle_tasks.ps1). install_tape_tasks.ps1 registers it
#              with -User and no logon type, which only runs while that user holds a desktop
#              session; vol_archive reads public CBOE series and the desk's parquets and needs no
#              terminal IPC, so S4U is the shape that keeps it running on a headless box.
#
# IDEMPOTENT. Without -IfMissing it replaces any existing registration with exactly this one. With
# -IfMissing it does nothing when the task exists (the Adopt-And-Seal.ps1 ensure-task form).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_vol_archive_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_vol_archive_task.ps1 -IfMissing
param(
    [switch] $IfMissing,
    [string] $Python = 'py',
    [string] $RunAs = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME)
)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-VolArchive'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Organ    = Join-Path $DeskRoot 'recorders\vol_archive.py'
if (-not (Test-Path $Organ)) { throw "vol_archive.py missing at $Organ" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute $Python -Argument '-3 -m recorders.vol_archive' `
    -WorkingDirectory $DeskRoot

# Hourly at :40, forever: a -Daily trigger whose Repetition is copied from a -Once trigger
# (install_cro_cycle_tasks.ps1). A -Once repetition ends when its duration ends, and PowerShell
# 5.1's -Daily set rejects -RepetitionInterval.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(40))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(40)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 50) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $RunAs -LogonType S4U -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Implied-vol and term-structure archive, hourly at :40: recorders.vol_archive appends one observation per instrument per cycle.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} runas={2} logon={3} every={4} next={5}" -f $t.TaskName, $t.State,
    $t.Principal.UserId, $t.Principal.LogonType, $t.Triggers[0].Repetition.Interval, $i.NextRunTime
if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
    Write-Host ("FATAL: {0} registered with no next run time" -f $TaskName)
    exit 4
}
