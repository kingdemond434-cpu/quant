# INSTALL THE MOAT MINER'S SCHEDULE (gap-fixer 2026-08-28).
#
# THE GAP. The trading box carried twenty scheduled tasks. Three of them RECORD the private
# Fusion tape (MT5-MoatRecorder, its watchdog, MT5-MoatFence) and a fourth publishes its coverage
# summary (MT5-MoatSilver, hourly). NONE of them MINED it: `desks/mt5/moat/moat_miner.py` -- the
# organ that turns the tape into testable hypotheses -- had no task at all. Its own state file
# showed `last_mined: 2026-08-25`, three days stale, because it only ever ran when a human
# remembered.
#
# So the desk was paying continuously for the expensive, irreversible half (2026 ticks cannot be
# re-recorded in 2029) and running the half that produces edge by hand. That is the sealed core's
# breach in its purest form -- "unmined proprietary data is edge already paid for and declined" --
# and III.16: unwired or idle is a defect, and a capability is only DONE when something runs it on
# a schedule and the run leaves an artifact.
#
# CADENCE. Hourly, matching MT5-MoatSilver. The miner takes a 40-symbol slice from a rotation
# cursor and there are 245 symbols, so a full pass closes every 7 hours and then begins again on
# newer ticks -- which is what "mined daily, never unexploited or forgotten" actually requires of
# a 245-symbol tape. Slower would leave most of the tape un-mined most of the time; the run costs
# ~90s and duplicate hypotheses are de-duplicated by id, so there is nothing to spend by going
# faster than the ground changes.
#
# Idempotent: re-running replaces the task rather than erroring. Mirrors MT5-MoatSilver's exact
# security context (same SID, S4U, HighestAvailable) so it runs under the identical principal as
# every other MT5 task rather than inventing a new one.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_moat_miner_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-MoatMiner'
$Script   = 'C:\opt\quant\desks\mt5\moat\moat_miner.py'
$Log      = 'C:\opt\quant\desks\mt5\logs\MT5-MoatMiner.log'

# Take the principal from MT5-MoatSilver rather than hardcoding a SID: the two organs are two
# halves of one loop and must never drift apart in identity or rights.
$template = Get-ScheduledTask -TaskName 'MT5-MoatSilver'
$userId   = $template.Principal.UserId

$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/d /s /c "py -3 {0} >> {1} 2>&1"' -f $Script, $Log)

$trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(1))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(1)) `
    -RepetitionInterval (New-TimeSpan -Hours 1)).Repetition

$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest

# StartWhenAvailable so an hour missed to a reboot is caught up rather than silently skipped --
# a schedule that loses runs to downtime reports the same artifact age as one that is broken.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Mine the private Fusion tape into testable hypotheses (rotation cursor over the whole 245-symbol tape; RESEARCH 6c-bis). Installed 2026-08-28: the tape was recorded on three schedules and mined on none.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval
