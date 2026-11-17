# Register MT5-LiveWire: first-party official feeds into the fast lane, every 2 minutes.
#
# live_wire.py --once --trigger polls every DUE feed in desks\mt5\data\live_wire_feeds.json whose
# terms verdict is OK (robots-gated, conditional GET, per-feed poll_every_s), appends new items to
# desks\mt5\data\news_captures.jsonl, and -- when it captured anything -- runs
# news_event_stream's fast lane in-process so the world state and the allocator re-solve request
# move within minutes. Writes desks\mt5\reports\LIVE_WIRE.json every pass.
#
# NOT A DAEMON (L0295): each run is one bounded pass and exits, so the 2-minute repetition with
# IgnoreNew never stacks and the 10-minute limit is never the normal exit path. The hourly leg
# `live_wire` runs the same pass; the organ's job lock makes an overlap a stand-down, not a race.

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'desks\mt5\research\live_wire.py --once --trigger >> C:\opt\quant\desks\mt5\logs\MT5-LiveWire.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
             -RepetitionInterval (New-TimeSpan -Minutes 2)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable

# S4U: headless, survives logoff and reboot, no password stored (the house pattern of
# install_cro_cycle_tasks.ps1 / install_contract_terms_task.ps1). An Interactive token would leave a
# 2-minute live wire silent whenever Administrator is logged off.
$principal = New-ScheduledTaskPrincipal -UserId 'Administrator' -LogonType S4U -RunLevel Highest

Register-ScheduledTask -TaskName 'MT5-LiveWire' -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-LiveWire'
Write-Output ("MT5-LiveWire registered: " + $t.State)
