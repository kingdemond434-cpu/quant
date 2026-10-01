# Register MT5-BoxHeartbeat: the trading box's outside alarm, every 5 minutes.
#
# box_heartbeat.py pings the box's own healthchecks.io check (URL in
# data\secrets\box_heartbeat_url.json, never in the repo) when every organ is fresh, and POSTs
# /fail naming the stale ones when not. healthchecks.io pages when the pings STOP, so a box that
# lost power, network or its scheduler is caught by a machine that is not the box. Without the
# secret it records NOT_ARMED and exits 0; arming is dropping that one file.
#
# IgnoreNew: a hung ping never stacks a second run. The 2-minute limit bounds a dead network.

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'desks\mt5\scripts\box_heartbeat.py >> C:\opt\quant\desks\mt5\logs\MT5-BoxHeartbeat.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
             -RepetitionInterval (New-TimeSpan -Minutes 5)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-BoxHeartbeat' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-BoxHeartbeat'
Write-Output ("MT5-BoxHeartbeat registered: " + $t.State)
