# INSTALL THE WORLD SENSOR'S 24/7 NEWS RESIDENT (2026-10-06).
#
# THE GAP, MEASURED. `research/news_event_stream.py` ran only as one `--once` leg of the macro
# department's hour, kept the 400 newest items of each pass and dropped the rest, and wrote
# re-solve requests nothing read. runtime_state.json (2026-09-30) showed leg:news_event_stream
# STALE. A tanker seizure at :05 reached the world state at the next hour at best.
#
# WHAT THIS REGISTERS. `news_event_stream.py --resident --interval-s 60`: a cursor-driven pass
# every minute over moat captures, news captures, the seat intelligence and the GDELT event and
# translingual vaults, with NO item cap (what a pass cannot reach is spilled to the next one),
# writing the sensor ledger, reports/WORLD_SENSOR_INTAKE.json and the sequenced
# allocator_resolve_request.json that MT5-AllocatorPulse watches.
#
# SINGLETON. The module holds its own lock (data/locks), so the hourly `--once` leg and this
# resident never run a pass concurrently; the trigger below is a KEEP-ALIVE (at startup, then
# every 10 minutes with IgnoreNew), the same shape as the Moat and Department residents.
#
# Idempotent: re-running replaces the task. Principal from MT5-MoatSilver, never a hardcoded SID.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_news_resident_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-NewsResident'
$Root     = 'C:\opt\quant\desks\mt5'
$Log      = 'C:\opt\quant\desks\mt5\logs\MT5-NewsResident.log'

$template = Get-ScheduledTask -TaskName 'MT5-MoatSilver'
$userId   = $template.Principal.UserId

$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/d /s /c "cd /d {0} && py -3 research\news_event_stream.py --resident --interval-s 60 >> {1} 2>&1"' -f $Root, $Log)

$boot = New-ScheduledTaskTrigger -AtStartup
$start = (Get-Date).AddMinutes(1)
$keep = New-ScheduledTaskTrigger -Once -At $start
$keep.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition

$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest

# No execution limit: it is a resident. IgnoreNew: the keep-alive never starts a second copy.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($boot, $keep) `
    -Principal $principal -Settings $settings `
    -Description 'World sensor news resident: cursor-driven, uncapped intake every 60 s into the sensor ledger, world state and the sequenced allocator re-solve request. Installed 2026-10-06: the stream ran only as an hourly leg capped at 400 items.' | Out-Null

Start-ScheduledTask -TaskName $TaskName
$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1}" -f $t.TaskName, $t.State
