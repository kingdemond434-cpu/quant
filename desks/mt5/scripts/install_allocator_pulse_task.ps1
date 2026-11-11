# Register MT5-AllocatorPulse: the allocator's 24/7 reaction resident (box_tasks.manifest).
#
# allocator_trigger.py --resident polls the decision inputs (MACRO_VIEW, regime_state,
# REGIME_ROUTER, sleeve registry, gateway_state, NET_EDGE and news_event_stream's
# allocator_resolve_request.json) every 20 s and fires `pf_allocator --mode fast` when one of them
# carries a real state change. A change stays PENDING until a landed decision echoes the input
# versions it consumed, so a debounced or failed solve is retried rather than lost. Latency per
# trigger kind is published in reports/ALLOCATOR_REACTION.json.
#
# DECLARED SINCE 2026-09-23 AND NEVER INSTALLED: the manifest carried installer="NONE", so the
# pulse never ran on the box and the hourly leg was the only path from news to sizing.
#
# KEEP-ALIVE SHAPE: the task fires at startup and every 5 minutes; IgnoreNew means a running
# resident is never stacked, so the 5-minute repetition only restarts a resident that died.
# No execution time limit (a resident is meant to run forever).

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'desks\mt5\research\allocator_trigger.py --resident ' +
  '>> C:\opt\quant\desks\mt5\logs\MT5-AllocatorPulse.log 2>&1')

$startup = New-ScheduledTaskTrigger -AtStartup
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(1) `
            -RepetitionInterval (New-TimeSpan -Minutes 5)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-AllocatorPulse' -Action $action `
  -Trigger @($startup, $repeat) -Settings $settings -User 'Administrator' -RunLevel Highest `
  -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-AllocatorPulse'
Write-Output ("MT5-AllocatorPulse registered: " + $t.State)
