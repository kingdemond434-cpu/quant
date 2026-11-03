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
# Idempotent: re-running replaces the task rather than erroring.
#
# THE PRINCIPAL IS THE TERMINAL'S DESKTOP OWNER, LOGGED ON INTERACTIVELY (2026-10-29). This used
# to copy MT5-MoatSilver's UserId with LogonType S4U. MoatSilver is a SYSTEM task, and S4U runs
# outside any desktop session anyway, so the recorder sat in Session 0 while terminal64 lived in
# the trading user's session 2: MetaTrader's IPC endpoint is session-bound, `initialize` failed
# every hour, and MT5-ContractTerms returned rc 1 (behind a NameError in tape.py's error path that
# hid the real reason). Same rule as MT5-Gateway, E8-Gold and the FTMO reader: a task that
# imports MetaTrader5 runs as the interactive user. The owner is read from MT5-TerminalBoot, as
# Install-QuantWindows.ps1 does, or passed with -InteractiveUser. SYSTEM and any machine account
# (a name ending in `$`) are refused outright.
# tests/ops/test_mt5_tasks_run_interactive.py fences every installer for this.
#
# AN INTERACTIVE TASK DOES NOT FIRE WHILE ITS USER IS LOGGED OFF. That is the trade: the terminal
# it reads is not running then either, so there is nothing to record, but a silent task must not
# read as a healthy one. ops/organ_contract.py holds MT5-ContractTerms to
# reports/BROKER_SWAPS_FRESHNESS.json, which tape.py rewrites every pass, so a logged-off desk (or
# a task that never fires) ages into FAILING on the board instead of going quiet.
#
# THE BOX MUST RE-RUN THIS INSTALLER after adopting the change -- a principal is fixed at
# registration, so the live task keeps its old SYSTEM/S4U identity until then. From an elevated
# shell IN THE TERMINAL OWNER'S OWN DESKTOP SESSION (not as SYSTEM):
#   powershell -NoProfile -ExecutionPolicy Bypass -File C:\opt\quant\desks\mt5\scripts\install_contract_terms_task.ps1
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_contract_terms_task.ps1 [-InteractiveUser <name>]

[CmdletBinding()]
param([string] $InteractiveUser)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-ContractTerms'
$Root     = 'C:\opt\quant\desks\mt5'
$Log      = 'C:\opt\quant\desks\mt5\logs\MT5-ContractTerms.log'

if (-not $InteractiveUser) {
    $terminalTask = Get-ScheduledTask -TaskName 'MT5-TerminalBoot' -ErrorAction SilentlyContinue
    if ($terminalTask -and $terminalTask.Principal.UserId) {
        $InteractiveUser = $terminalTask.Principal.UserId
    } else {
        $InteractiveUser = $env:USERNAME
    }
}
# A NAME ENDING IN `$` IS THE MACHINE ACCOUNT, NOT A DESKTOP USER (audit, 2026-10-29). Run as
# SYSTEM (an elevated deploy step, a scheduled re-installer) $env:USERNAME is `HOST$`: the task
# registers cleanly, LogonType Interactive never matches a logged-on session, and it never fires.
# Refuse it with SYSTEM itself, however either is spelled.
$bareUser = ($InteractiveUser -split '\\')[-1]
if (-not $InteractiveUser -or $bareUser.EndsWith('$') -or
        $bareUser -in @('SYSTEM', 'S-1-5-18', 'LOCAL SERVICE', 'NETWORK SERVICE')) {
    throw "$TaskName needs the MT5 terminal's interactive desktop owner (got '$InteractiveUser'); pass -InteractiveUser"
}

# `-m mt5desk.tape` from the desk root, not a file path: the module resolves its own DATA root
# from __file__ and importing it as a module is how tape.py documents itself being run.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/d /s /c "cd /d {0} && py -3 -m mt5desk.tape --terms-only >> {1} 2>&1"' -f $Root, $Log)

$trigger = New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(1))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(1)) `
    -RepetitionInterval (New-TimeSpan -Hours 1)).Repetition

$principal = New-ScheduledTaskPrincipal -UserId $InteractiveUser -LogonType Interactive -RunLevel Highest

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
"installed {0}: state={1} interval={2} principal={3}/{4}" -f $t.TaskName, $t.State, `
    $t.Triggers[0].Repetition.Interval, $t.Principal.UserId, $t.Principal.LogonType
