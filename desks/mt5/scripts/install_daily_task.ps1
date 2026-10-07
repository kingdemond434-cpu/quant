# Register MT5-Daily: desks\mt5\research\daily_cycle.py, once a day at 23:50 box-local time.
#
# WHY THIS FILE HAD TO EXIST (DECAY-12). box_tasks.manifest has declared MT5-Daily since the
# manifest was written, with installer="NONE": the task existed on the box only because somebody
# once clicked it into the Task Scheduler, and a rebuilt or re-imaged box would come up without
# it and nothing would say so. drift_monitor (reports\DRIFT.json -- the allocator's per-sleeve
# decay hazard and its crisis-world share) is a step of this chain and runs nowhere else, so a box
# without this task silently feeds the allocator a hazard that ages until staleness_clamp holds the
# whole book. This makes the task reproducible from the repo like its siblings.
#
# THE TIME LIMIT IS DERIVED FROM WHAT THE CHAIN DOES, NOT PICKED. daily_cycle.STEPS is ~36 steps;
# its research steps were MEASURED on this box at 9,056 s (daily_cycle.main's own comment,
# 2026-09-30), and deepen_bars carries its own --budget-s 1500 on top. That is ~10,600 s, under
# three hours; four hours (PT4H) leaves a third again for a slow terminal and still ends twenty
# hours before tomorrow's trigger. A run that hits the limit is not lost: daily_cycle writes its
# stamp after EVERY step, so the next invocation (tomorrow's, or hourly_cycle.daily()'s 900 s
# call) runs only the steps the stamp does not name.
#
# IgnoreNew: a run still going at the next trigger is never stacked. daily_cycle self-guards on a
# UTC date stamp, so a manual or hourly call on the same day is a cheap no-op, not a second run.
# StartWhenAvailable: a box that was down at 23:50 runs the day's chain when it comes back.

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'desks\mt5\research\daily_cycle.py >> C:\opt\quant\desks\mt5\logs\MT5-Daily.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Daily -At '23:50'

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 4) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-Daily' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-Daily'
Write-Output ("MT5-Daily registered: " + $t.State)
