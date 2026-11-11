# Register MT5-CacheWarm: precompute the judge's series cache on cycles the box can spare.
#
# THE TRIGGER, LIMIT, INSTANCE AND PRIORITY VALUES BELOW ARE THE TRUTH; each is tied to how long
# a run lasts. THE PRINCIPAL IS NOT CHANGED HERE: the action runs Administrator's per-user
# Python314, whose site-packages a SYSTEM principal cannot see, so this installer registers as
# Administrator, as it always has. The 2026-10-28 box read reported the live task as SYSTEM --
# CONFIRM the live principal (`schtasks /Query /TN MT5-CacheWarm /V /FO LIST`, "Run As User")
# before re-running this; the XML route in the README keeps whatever principal the task has and
# is the preferred way to change only the settings.
#
#   * HOURLY TRIGGER. A run ends by itself within 3,540 s of starting: budget 3,300 s plus a
#     240 s grace (WARM_BUDGET_SEC / WARM_GRACE_SEC in warm_gauntlet_cache.py). A watchdog
#     hard-stops it there, prints `CacheWarm END`, writes WARM_GAUNTLET.json and exits rc 3.
#     So a run never overlaps the next trigger. (This installer used to say every 30 minutes,
#     which a 55-minute run would overlap by design.)
#   * EXECUTION TIME LIMIT 1h15m, ABOVE 3,540 s. It is an outer backstop only. It must never
#     be the thing that ends a healthy run: the scheduler ends cmd.exe, and a python child
#     that outlives it keeps the log open, so the next trigger fails with result 1 and writes
#     nothing. The old 2 h and 4 h limits let a stalled run hold every trigger for hours.
#   * IgnoreNew. A trigger that fires while a run is still alive is refused (0x800710E0)
#     instead of stacking a second run. job_lock refuses a duplicate as well.
#   * PRIORITY 7 (BELOW_NORMAL). This is the scheduler default and the miners' class. The
#     parent stays at BELOW_NORMAL, and the build workers drop themselves to IDLE.
#     Never set a higher class.
#
# Memory admission is MEASURED. The parent declares its own p75 (about 4.4 GB on the trading
# box), and workers are sized on their measured p75. Until one is measured, 4,500 MB is used.
#
# Re-running this on a live box has failed with "Access is denied" before. To change only
# the settings, use the XML route in patches/judge_cachewarm_fix/v1.1/README.md. It uses
# schtasks.exe, not CIM, because CIM has hung on the trading box.

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant\desks\mt5 && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'scripts\warm_gauntlet_cache.py >> C:\opt\quant\desks\mt5\logs\MT5-CacheWarm.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
             -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 1 -Minutes 15) -StartWhenAvailable `
              -Priority 7

Register-ScheduledTask -TaskName 'MT5-CacheWarm' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-CacheWarm'
Write-Output ("MT5-CacheWarm registered: " + $t.State)
