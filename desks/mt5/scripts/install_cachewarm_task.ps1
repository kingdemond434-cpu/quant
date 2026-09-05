# Register MT5-CacheWarm: precompute sweep series whenever the box has room to spare.
#
# WHY EVERY 30 MINUTES, AND WHY THAT IS NOT AGGRESSIVE. The warmer refuses to start unless the
# box has 900MB free (median of three readings, so a sawtooth trough cannot fool it), and it
# stops mid-run the moment free memory drops under 1.2GB. It is therefore self-regulating: on a
# busy box it costs one process start and exits in seconds, and on an idle box it converts that
# idleness into cache the next sweep does not have to compute.
#
# Frequent attempts are the right shape precisely BECAUSE most of them will decline. The window
# where this work is free -- searcher between symbols, no sweep running -- is short and
# unpredictable, and a job that only tries twice a day will miss it. Optional work should ask
# often and yield instantly, not ask rarely and insist.
#
# IgnoreNew: if a warm run is already going, the trigger does not stack a second one.

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant\desks\mt5 && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'scripts\warm_gauntlet_cache.py >> C:\opt\quant\desks\mt5\logs\MT5-CacheWarm.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(7) `
             -RepetitionInterval (New-TimeSpan -Minutes 30)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-CacheWarm' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-CacheWarm'
Write-Output ("MT5-CacheWarm registered: " + $t.State)
