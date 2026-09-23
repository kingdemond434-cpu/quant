# THE GRID FILLER GETS ITS OWN HOUR (2026-09-23).
#
# WHY IT NEEDS ONE, measured on the trading box rather than assumed. `independence_intake` is
# registered as an hourly_cycle leg in department `meta`, and `in_plan` says yes -- so on paper
# it is clocked. In practice it had NEVER run: the compute ledger held zero rows for it, and the
# reason is that `MT5-HourlyCore` runs with HOURLY_PLAN=core (the leg is not a core leg, so that
# task skips it with no ledger row at all), and every non-core leg reaches a clock only through
# `department_resident.py --dept meta`, whose pass on this box took 5,676 to 10,800 seconds --
# eight passes in twenty-one hours, two of them killed at the 3h timeout. The leg sits at line
# ~3,683 of a 4,464-line cycle, so a timed-out meta pass never reaches it at all. It first fired
# at 22:03 UTC, about eighty-five minutes into the pass that followed its landing.
#
# ONE ROW AN HOUR IS NOT WHAT THIS ORGAN IS FOR. It publishes the family x instrument x horizon
# grid's occupancy, ranks every reachable empty cell as a target, and TRANSPLANTS families' own
# rules onto them -- 32,585 cells in one pass on the day this was written, taking occupancy from
# 7.25% to 61.2%. A filler that runs eight times a day at best, and not at all when an unrelated
# department's pass overruns, is a breadth organ on somebody else's clock.
#
# WHAT THIS COSTS: 6.5 seconds on a full grid, ninety on one with thirty thousand cells to fill.
# That is why it can have its own hour rather than waiting for a three-hour pass -- and why the
# `MultipleInstances IgnoreNew` below is belt and braces rather than a real concern.
#
# THE hourly_cycle LEG STAYS REGISTERED. Running twice in an hour costs nothing: every cell goes
# through `enqueue_candidate`, which de-duplicates on content hash, so a second pass over ground
# already filled raises search counts and creates nothing. Two clocks on an idempotent organ is
# redundancy, not a race.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_independence_intake_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-IndependenceIntake'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Organ    = Join-Path $DeskRoot 'research\independence_intake.py'
if (-not (Test-Path $Organ)) { throw "independence_intake.py missing at $Organ" }

$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python.exe -ErrorAction Stop).Source
}
$LogDir = Join-Path $DeskRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'MT5-IndependenceIntake.log'

# --budget-s 600: the organ stops ITSELF and writes, and the task's limit sits above its own
# budget. A cap below an organ's budget truncates it at the same prefix every hour -- the defect
# that cost this desk eighty-four forward clocks (see LEG_BUDGET_SEC in hourly_cycle.py).
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument `
    ('/d /s /c ""{0}" -W ignore "{1}" --once --budget-s 600 >> "{2}" 2>&1"' -f $Python, $Organ, $Log)

# A DAILY trigger repeating hourly for one day, never a -Once trigger with a long duration: the
# scheduler folds a long duration into a fixed number of days and the repetition then EXPIRES
# with `Next Run Time: N/A` and nothing to say so (measured 2026-09-22 on this box for
# MT5-AdoptRelease). At :42, clear of the :12 adoption and the :05/:20/:35/:50 sync slots.
$at = (Get-Date).Date.AddMinutes(42)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $at `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew

# SYSTEM, ServiceAccount: the box's tasks run as SYSTEM. An Interactive principal only fires
# while that user holds a desktop session, and the organ then dies with the session.
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Publish grid occupancy and transplant family rules onto every reachable empty cell of the family x instrument x horizon grid." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

# THE FIRST PASS IS NOW, not at :42: an hour of an unfilled grid is an hour of judge time spent
# on ground the desk already holds.
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 20
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"log: {0}" -f $Log
