# THE REAPER WAS BUILT AND PUT ON NO CLOCK (measured 2026-09-24, and it cost this box a day).
#
# `scripts/reap_hung_git_writers.py` exists, `libs/ops/git_writer_lock.reap_hung_writers` exists,
# and `scripts/check_scheduled_tasks.py::stuck_writers` has named the offending pids every pass
# for weeks. NOTHING RAN ANY OF THEM. Not a box task, not a PowerShell wrapper, not a cycle leg.
# That is III.16 with the reaper's own words used against it: "an organ that reports forever and
# changes nothing", written in the file that then reported forever and changed nothing.
#
# WHAT IT COST, measured today. Two `git push` chains had been STOPPED for 6.0 h and 6.9 h -- 13
# processes, each chain ending in `git-credential-manager get` waiting on a credential prompt
# that no session-0 scheduled task can ever answer. They held the writer mutex every ship step
# serialises on. A hand-run reap cleared all 13 in one pass. A hand-run reap is not a fix: the
# next headless push wedges the same way, and nothing is watching.
#
# EVERY FIFTEEN MINUTES, AND WHY THAT IS SAFE. The reaper kills a process only when all four of
# these hold: it is git, ssh or one of git's own helper binaries (never `sshd`); it is older than
# 30 minutes, which is past every legitimate writer's OWN timeout (adopt waits 540 s, shadow-sync
# 600 s); it moved ZERO CPU and ZERO bytes of I/O across a 15-second sample, so a slow `git gc`
# is spared and a stopped one is not; and it is not this process or one of its ancestors. A box
# with nothing hung is a process start and a CLEAR verdict in `reports/GIT_WRITER_REAP.json`.
#
# Asking often and yielding instantly is the right shape here for the same reason MT5-CacheWarm
# uses it: the window where the mutex is wrongly held is unpredictable, and a job that looks
# twice a day leaves the desk silently unable to ship for up to twelve hours.

param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$py = 'C:\Program Files\Python314\python.exe'

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"' + $py + '" -u scripts\reap_hung_git_writers.py --apply ' +
  '>> C:\opt\quant\desks\mt5\logs\MT5-ReapGitWriters.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(9) `
             -RepetitionInterval (New-TimeSpan -Minutes 15)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable `
              -Priority 7

if ($DryRun) {
  Write-Output 'DRYRUN would register MT5-ReapGitWriters every 15m, PT10M limit, priority 7'
} else {
  Register-ScheduledTask -TaskName 'MT5-ReapGitWriters' -Action $action -Trigger $trigger `
    -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
  $t = Get-ScheduledTask -TaskName 'MT5-ReapGitWriters'
  Write-Output ('MT5-ReapGitWriters registered: ' + $t.State +
                ' priority=' + $t.Settings.Priority)
}
