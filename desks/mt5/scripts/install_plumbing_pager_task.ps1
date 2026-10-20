# REGISTER THE PLUMBING PAGER, AND RUN IT NOW (audit HOLD on 018de05c5, 2026-10-20).
#
# WHY THE BOX PAGES ITSELF. scripts/run_alerts.py, the desk's pager, ran only from the VPS cron,
# and the VPS runs the orphan desk-sync-clean, which never receives what this pager reads:
# desks/mt5/reports/PLUMBING_WATCHDOG.json (box-local, gitignored), docs/research/PLUMBING_ALERTS.md
# and desks/mt5/reports/JUDGING_RATE.json. Run there, it could only page UNMEASURED forever and
# never see a real stall. So the box runs `run_alerts.py --box` from its own files: CRITICAL
# plumbing rows, a stalled judge (no new verdict in JUDGE_STALL_H), and UNMEASURED inputs, each
# re-paged every REPAGE_H while still failing, through the existing ntfy sender.
#
# THE SECRET. The ntfy topic is read from data\secrets\ntfy.json (or desks\mt5\data\secrets\),
# the same file the VPS pager uses: copy it onto the box once, never into the repo. Without it
# the pass logs "NOT ARMED", sends nothing, creates no topic, and exits 2, so the task's Last
# Result shows the failure instead of a green run that paged no one.
#
# THE TRIGGER SHAPE copies install_plumbing_watchdog_task.ps1 on purpose: a DAILY trigger
# repeating every 15 minutes for one day (a -Once trigger with a long duration expired on this
# box and stopped adoption for four days). Offset to :10, three minutes after the watchdog's :07,
# so each pass reads a fresh report. SYSTEM / ServiceAccount so it fires with nobody logged in.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_plumbing_pager_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-PlumbingPager'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Script   = Join-Path $RepoRoot 'scripts\run_alerts.py'
if (-not (Test-Path $Script)) { throw "run_alerts.py missing at $Script" }

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = 'python' }

$action = New-ScheduledTaskAction -Execute $python -Argument `
    ("-W ignore `"{0}`" --box" -f $Script) -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(10))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(10)) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# IgnoreNew: a hung push never stacks a second pass. Five minutes bounds a dead network
# (each push is 15 s at most).
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Page the principal every 15 minutes on CRITICAL plumbing defects, a stalled judge, and UNMEASURED plumbing/judge inputs (scripts/run_alerts.py --box)." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3} (2 = NOT ARMED: copy data\secrets\ntfy.json onto the box)" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"dedupe state: desks\mt5\logs\plumbing_pager_state.json"
