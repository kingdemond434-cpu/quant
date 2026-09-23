# INSTALL THE CONTRACT-TERMS RECORDER'S SCHEDULE (CRO cycle 2026-08-29).
#
# THE GAP, MEASURED. `desks/mt5/data/tape/contract_terms` held exactly ONE file on 2026-08-29:
# `2026-08-27.parquet`, 1,908 rows across 9 hourly observations. Nothing for Friday 2026-08-28 --
# a full trading day -- while the H1 bar parquets synced from the SAME Windows terminal carried
# that day's mtime. The terminal was up; only this recorder had stopped.
#
# It stopped because nothing was starting it. Three MT5 tasks record the tick tape and a fourth
# publishes coverage; the point-in-time financing leg had NO task and ran only when a human
# remembered, which is the same defect install_moat_miner_task.ps1 was written for one day
# earlier. `mt5desk.tape --terms-only` exists precisely so this cheap leg can be scheduled apart
# from the expensive tick pull -- the split was built and then never wired.
#
# WHY IT IS NOT COSMETIC. `symbol_info` reports TODAY's values and a past night's are unbuyable at
# any price: a field re-derived from tomorrow's registry silently re-prices yesterday's tape. The
# module's own measurement is that 81 of 248 symbols repriced inside a single three-day window, so
# a two-day gap is not a rounding error in the swap history -- it is a hole in it. The row now
# also carries `trade_mode` (3 = CLOSEONLY, a dated forced-exit instruction from the broker),
# `margin_initial` / `margin_maintenance` (announced deleveraging) and the stop-distance bounds,
# all of which were being dropped at zero saving from a call already being paid for.
#
# CADENCE. Hourly, matching MT5-MoatSilver. The run is seconds -- one `symbol_info` per symbol
# against an already-open terminal -- and rows are de-duplicated on (observed_at, symbol), so
# there is nothing to spend by running at the rate the terms can actually change.
#
# THE FENCE THAT NOTICES. scripts/max_audit.py::check_production gauges this tape on TRADING DAYS,
# not on age: the most recent fully-passed weekday must have a file. It cannot fire on a Saturday
# for being a Saturday, and it fires the morning after any missed trading day. Silence is no
# longer green.
#
# Idempotent: re-running replaces the task rather than erroring. Takes its principal from
# MT5-MoatSilver rather than hardcoding a SID, so the MT5 organs never drift apart in identity.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_contract_terms_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-ContractTerms'
$Root     = 'C:\opt\quant\desks\mt5'
$Log      = 'C:\opt\quant\desks\mt5\logs\MT5-ContractTerms.log'

$template = Get-ScheduledTask -TaskName 'MT5-MoatSilver'
$userId   = $template.Principal.UserId

# `-m mt5desk.tape` from the desk root, not a file path: the module resolves its own DATA root
# from __file__ and importing it as a module is how tape.py documents itself being run.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/d /s /c "cd /d {0} && py -3 -m mt5desk.tape --terms-only >> {1} 2>&1"' -f $Root, $Log)

$trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(1))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(1)) `
    -RepetitionInterval (New-TimeSpan -Hours 1)).Repetition

$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest

# StartWhenAvailable so an hour lost to a reboot is caught up rather than silently skipped -- a
# schedule that loses runs to downtime reports the same artifact age as one that is broken.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Record point-in-time broker financing and contract terms from the connected Fusion terminal (mt5desk.tape --terms-only). Installed 2026-08-29: the tape had one day on disk and no scheduler -- an unrecorded swap or margin reprice is unbuyable at any price.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval
