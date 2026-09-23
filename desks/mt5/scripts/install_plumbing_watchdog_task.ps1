# REGISTER THE PLUMBING WATCHDOG, AND RUN IT NOW (principal 2026-09-23).
#
# THE ORDER: "make the plumbing never ever permanently stop silently -- it must never move, fixes
# never silent or reverted." Five failures were measured on this box inside one day and every one
# of them was already being logged, correctly, to nothing. The watchdog is the reader those logs
# never had, and it is worth nothing at all unless it has a clock of its own.
#
# WHAT IT DOES. Registers MT5-PlumbingWatchdog -- every FIFTEEN minutes, offset to :07 so it does
# not land in the :05/:20/:35/:50 ShadowSync slots or on the :12 adoption -- running
# desks/mt5/research/plumbing_watchdog.py --once --apply --budget-s 180. It proves by observation
# that the adoption task exists and is enabled with a next run inside the hour, that HEAD descends
# from the branch tip, that the git-writer lock can be TAKEN right now, that no orphaned pool
# worker is holding commit, that every declared clock is present, that each producer/consumer pair
# agrees about its path, and that every registered fence has run. Then STARTS it, so the first
# pass happens now rather than at the next :07.
#
# THE TRIGGER SHAPE IS NOT A STYLE CHOICE. A DAILY trigger repeating every fifteen minutes for one
# day, never a -Once trigger with a long RepetitionDuration: MEASURED 2026-09-22, the scheduler
# folded MT5-AdoptRelease's long duration into `P9DT2H40M`, the repetition EXPIRED, Next Run Time
# went to N/A, and nothing shipped reached the box for four days. A daily trigger re-arms itself
# every midnight and has no end to expire. The watchdog that watches for that failure may not be
# registered in the shape that caused it.
#
# SYSTEM, ServiceAccount, RunLevel Highest: an Interactive principal only fires while that user
# holds a desktop session, and a watchdog that stops when somebody logs out is a watchdog that is
# absent exactly when nobody is looking.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_plumbing_watchdog_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-PlumbingWatchdog'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Script   = Join-Path $DeskRoot 'research\plumbing_watchdog.py'
if (-not (Test-Path $Script)) { throw "plumbing_watchdog.py missing at $Script" }

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = 'python' }

$action = New-ScheduledTaskAction -Execute $python -Argument `
    ("-W ignore `"{0}`" --once --apply --budget-s 180" -f $Script) -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(7))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(7)) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# StartWhenAvailable so a pass missed to a reboot is caught up rather than silently skipped;
# IgnoreNew so a slow pass is never stacked on itself; ten minutes because a watchdog pass that
# takes longer than that is itself the defect and belongs in the report, not in a second process.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Prove by observation every 15 minutes that the desk's plumbing is moving: adoption clock, git-writer lock, commit headroom, declared tasks, producer/consumer paths, fences." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"report: desks\mt5\reports\PLUMBING_WATCHDOG.json; escalations: docs\research\PLUMBING_ALERTS.md"
