# Register MT5-MergeDocket: research/merge_hypotheses.py every 30 minutes (idea 619).
#
# WHAT THE BOX RAN UNTIL THIS FILE (read off the box 2026-11-11, Desk health GV2,
# /mnt/project-files/reports/box_reads/mergedocket_task_gv2_2026-11-11.md). The task was
# registered by hand on 09-24 and had no installer in this repo:
#   cmd.exe /d /s /c cd /d C:\opt\quant\desks\mt5 && python ... merge_hypotheses.py
#       >> C:\opt\quant\desks\mt5\logs\MT5-MergeDocket.log 2>&1
#   SYSTEM / Highest, every PT30M, IgnoreNew, NO ExecutionTimeLimit (so the 72 h default).
#
# WHAT THAT COST. The 09:32Z stop ended the cmd.exe wrapper and left its python child
# (pid 36280, started 11-09 18:44Z) alive, still holding the shared log. Every later trigger
# then failed in the same second with 0x80070001 at the `>>` redirect. Python never started and
# nothing was written.
#
# WHAT CHANGES, AND WHY EACH IS SAFE:
#   * PYTHON IS THE ACTION, with no cmd.exe wrapper. The scheduler's stop then ends the process
#     that does the work, so a stop can no longer leave an orphan behind.
#   * --log-dir REPLACES `>>`. merge_hypotheses writes its own per-run file,
#     MT5-MergeDocket-<UTC>-<pid>.log, plus MT5-MergeDocket.latest.txt naming it, and prunes
#     files older than 14 days. No two runs share a file, so no run can block another's log.
#   * EXECUTION TIME LIMIT 36 h. This is an outer backstop only. Healthy runs have been measured
#     at about 27 h (local_converter.py notes), so the limit must sit above that and never end a
#     healthy run. It only shortens the 72 h default that let a hung run hold the docket for days.
#   * UNCHANGED: SYSTEM principal (Python314 under Program Files is machine-wide), Highest,
#     every 30 minutes, IgnoreNew. job_lock's exclusive_job still refuses a duplicate.
#
# Memory is admitted by the script itself (job_lock measured need, plus the families-step
# admission from #996), never by this file.
#
# Re-running a whole installer on a live box has failed with "Access is denied" before. This
# one touches one task. It uses schtasks.exe for the read-back, not CIM, because CIM has hung on
# the trading box.

$py   = 'C:\Program Files\Python314\python.exe'
$desk = 'C:\opt\quant\desks\mt5'

$action = New-ScheduledTaskAction -Execute $py `
  -Argument ('-u -W ignore research\merge_hypotheses.py --log-dir ' + $desk + '\logs') `
  -WorkingDirectory $desk

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
             -RepetitionInterval (New-TimeSpan -Minutes 30)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 36) -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName 'MT5-MergeDocket' -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

schtasks.exe /Query /TN MT5-MergeDocket /V /FO LIST | Select-String 'Status|Task To Run|Run As User|Repeat: Every'
