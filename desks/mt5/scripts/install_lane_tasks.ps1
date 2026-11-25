# THE FOUR LEGS TAKEN OFF THE HOURLY CORE PASS GET THEIR OWN TASKS (2026-11-25).
#
# MEASURED ON THE BOX: MT5-HourlyCore was killed at its PT55M limit on 5 of 5 runs -- plan 2,640 s,
# actual 3,092-4,597 s. `tier_s` was the killed leg every time (it started with 150-1,832 s left
# against its own 1,500 s cap), `replication_civilization` hit its 1,035 s cap with 0 of 1
# artifacts every run, `record_tape` took 41-1,594 s, and `compile_candidates` (720 s cap) was
# killed 8 of 8 times 11-20..11-24 so miner_candidates.json stayed at 2026-10-03.
#
# Each leg now runs `hourly_cycle.py --lane <lane>` on a task whose limit is its own
# (hourly_cycle.OWN_CLOCK_LEGS / LANE_LEGS). Nothing is dropped; the legs are in no cycle plan.
#
#   MT5-Compiler     :28  PT60M  compile (budget 2100 s) then merge_hypotheses
#   MT5-TapeRecord   :08  PT40M  broker-native tick tape + triangle tape (irreversible capture)
#   MT5-TierS        :18  PT45M  full Tier S pass (its own cap 1,500 s)
#   MT5-Replication  :48  PT45M  reports/REPLICATION.json (budget 1,500 s; was 900 s and killed)
#
# DAILY trigger repeating hourly for one day, never -Once with a long duration (the scheduler
# folds that into days and the repetition expires silently). IgnoreNew: a run in progress absorbs
# the triggers under it. SYSTEM, priority 7 (below the live E8 tasks, like the judge).
#
#   -IfMissing  register only tasks that do not exist (what Adopt-And-Seal calls: re-registering
#               live tasks has failed with "Access is denied")
#   -DryRun     print what would be registered and touch nothing
param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Cycle    = Join-Path $DeskRoot 'research\hourly_cycle.py'
$py       = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $py)) { $py = (Get-Command python.exe -ErrorAction Stop).Source }
if (-not (Test-Path $Cycle)) { throw "hourly_cycle.py missing at $Cycle" }
$LogDir = Join-Path $DeskRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

$lanes = @(
    @{ Task = 'MT5-Compiler';    Lane = 'compiler';    Minute = 28; LimitMin = 60 },
    @{ Task = 'MT5-TapeRecord';  Lane = 'tape';        Minute = 8;  LimitMin = 40 },
    @{ Task = 'MT5-TierS';       Lane = 'tier_s';      Minute = 18; LimitMin = 45 },
    @{ Task = 'MT5-Replication'; Lane = 'replication'; Minute = 48; LimitMin = 45 }
)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

foreach ($l in $lanes) {
    $exists = [bool](Get-ScheduledTask -TaskName $l.Task -ErrorAction SilentlyContinue)
    if ($IfMissing -and $exists) { "{0}: already registered; nothing to do" -f $l.Task; continue }
    $log = Join-Path $LogDir ($l.Task + '.log')
    $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
        '/d /s /c cd /d "' + $DeskRoot + '" && "' + $py + '" -u -W ignore "' + $Cycle +
        '" --lane ' + $l.Lane + ' >> "' + $log + '" 2>&1') -WorkingDirectory $DeskRoot
    $start = (Get-Date).Date.AddMinutes($l.Minute)
    $trigger = New-ScheduledTaskTrigger -Daily -At $start
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
        -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes $l.LimitMin) -Priority 7
    if ($DryRun) {
        'DRYRUN would register {0}: hourly at :{1:00}, SYSTEM, PT{2}M, priority 7, --lane {3}' -f `
            $l.Task, $l.Minute, $l.LimitMin, $l.Lane
        continue
    }
    if ($exists) { Unregister-ScheduledTask -TaskName $l.Task -Confirm:$false }
    Register-ScheduledTask -TaskName $l.Task -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings `
        -Description ("hourly_cycle own-clock lane '" + $l.Lane + "' (OWN_CLOCK_LEGS), hourly") | Out-Null
    $t = Get-ScheduledTask -TaskName $l.Task
    "installed {0}: state={1} lane={2}" -f $t.TaskName, $t.State, $l.Lane
}
