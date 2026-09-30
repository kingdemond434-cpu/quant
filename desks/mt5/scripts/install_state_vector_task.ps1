# TWO SCHEDULING FACTS, MEASURED ON THE TRADING BOX 2026-09-24.
#
# 1. `state_vector` CANNOT FIT INSIDE THE HOURLY PASS AND NEVER COULD.
#    `MT5-HourlyCore` carries ExecutionTimeLimit=PT40M and the leg rotation plans into 1,920s of
#    it. The `state_vector` leg held a 900s budget -- 47% of the whole planning budget -- and the
#    artifact it produced, data\state_vector.json, was 26.6 HOURS OLD. It was not slow; it was
#    impossible. Measured per HMM fit on this box: weekly 7.5s, daily 33.2s, H4 48.0s, H1 45.4s,
#    M15 69.5s, M5 94.7s, over a planned roster of 115 fits = 5,603s. Nothing in that roster is
#    removed here -- the same 18 book symbols on the same 6 clocks -- it is given a clock that
#    fits it, and the hourly pass gets its 900s back.
#
#    Every 30 minutes with IgnoreNew is the right shape: a run in progress simply absorbs the
#    triggers under it, so the artifact refreshes as fast as the work allows and never faster.
#    ExecutionTimeLimit PT2H sits ABOVE the organ's own --budget-s 5400, because a cap BELOW an
#    organ's own budget is the truncated-job defect this desk has now paid for twice: the organ
#    stops itself and WRITES, rather than being killed holding everything it computed.
#
# 2. THE JUDGE HAD NO PRIORITY OVER ANYTHING.
#    A process census of the box found 96 of 104 desk processes at BELOW_NORMAL and 8 at NORMAL.
#    `external_gauntlet.py` was one of the 96 -- exactly level with all 23 research department
#    residents, which set BELOW_NORMAL deliberately. A sweep that is killed loses EVERYTHING it
#    computed (65 cells that passed all ten gates were discarded that way), while a research leg
#    that is descheduled loses one pass and leads the next. Those two are not worth the same, and
#    the scheduler was treating them as if they were.
#
#    So MT5-Gauntlet is raised to task priority 4 (NORMAL_PRIORITY_CLASS) and NOTHING is lowered.
#    That is the whole change: the judge now wins a contended core against the research fleet,
#    and the fleet keeps every core it has when the judge is not running.
#
#    THE LIVE TERMINAL IS NOT TOUCHED. terminal64.exe measures BELOW_NORMAL on this box, which is
#    a real finding and somebody's decision to make -- but not this script's, and not a research
#    session's. The judge already reserves cores for it (external_gauntlet._worker_count), which
#    is the guard that makes raising the judge safe without raising anything else.
#
#    -WhatIf-style dry run: pass -DryRun to print what would change and touch nothing.

param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$py = 'C:\Program Files\Python314\python.exe'

# ---------------------------------------------------------------- 1. MT5-StateVector
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant\desks\mt5 && ' +
  '"' + $py + '" -u -W ignore research\state_vector_build.py --budget-s 5400 ' +
  '>> C:\opt\quant\desks\mt5\logs\MT5-StateVector.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(3) `
             -RepetitionInterval (New-TimeSpan -Minutes 30)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable `
              -Priority 7

if ($DryRun) {
  Write-Output 'DRYRUN would register MT5-StateVector every 30m, PT2H limit, priority 7'
} else {
  Register-ScheduledTask -TaskName 'MT5-StateVector' -Action $action -Trigger $trigger `
    -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
  $t = Get-ScheduledTask -TaskName 'MT5-StateVector'
  Write-Output ('MT5-StateVector registered: ' + $t.State +
                ' priority=' + $t.Settings.Priority)
}

# ------------------------------------------------- 2. the judge's priority, and only the judge's
# Mutate the LIVE settings object rather than rebuilding one: Set-ScheduledTask -Settings
# replaces the whole set, and rebuilding it by hand is how a trigger or a time limit gets lost.
$g = Get-ScheduledTask -TaskName 'MT5-Gauntlet'
$before = $g.Settings.Priority
if ($DryRun) {
  Write-Output ('DRYRUN MT5-Gauntlet priority ' + $before + ' -> 4')
} elseif ($before -eq 4) {
  Write-Output 'MT5-Gauntlet already at priority 4; nothing changed'
} else {
  $g.Settings.Priority = 4
  Set-ScheduledTask -InputObject $g | Out-Null
  $after = (Get-ScheduledTask -TaskName 'MT5-Gauntlet').Settings.Priority
  Write-Output ('MT5-Gauntlet priority ' + $before + ' -> ' + $after +
                ' (4 = NORMAL_PRIORITY_CLASS; the research fleet stays at 7)')
}
