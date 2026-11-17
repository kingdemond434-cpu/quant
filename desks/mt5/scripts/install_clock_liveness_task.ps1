# REGISTER MT5-ClockLiveness -- THE FORWARD-CLOCK CENSUS ON ITS OWN CLOCK (2026-10-13).
#
# THE GAP. `research\clock_liveness.py` (which forward clocks are accruing, frozen, retired or
# kept while their certificate is re-minted, and the repairs for the frozen ones) ran only as a
# leg inside the hourly pass. From 2026-10-12 07:00Z MT5-Hourly returned 0x800710E0 every hour,
# killed before it reached the leg, and reports\CLOCK_LIVENESS.json sat 44 hours old reading
# retire=[] and unbacked_found=0 -- a clean answer that nobody had measured.
#
# WHAT IT DOES. Hourly at :28 box-local, `research\clock_liveness.py --once --budget-s 300` from
# the desk root, SYSTEM. :28 because this organ rewrites shadow lanes (retire_unbacked/retire_gone)
# and MT5-Healers rewrites shadow_state.json in place at :48; :28 is also clear of the :05/:12/:20
# repository writers, and of MT5-HourlyCore, which starts at :36 and may run to :16.
# The leg is in hourly_cycle.OWN_CLOCK_LEGS, so the pass no longer runs it and the two can
# never repair the same clock concurrently. IgnoreNew: a slow pass absorbs the next trigger.
# FIFTEEN MINUTES sits above the organ's own 300 s budget, so the organ stops itself and WRITES
# rather than being killed holding what it computed.
#
# IDEMPOTENT. -IfMissing does nothing when the task exists; Adopt-And-Seal.ps1 calls it that way
# on every adoption, so the box gains the task within the hour of adopting this commit.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_clock_liveness_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_clock_liveness_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-ClockLiveness'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Organ    = Join-Path $DeskRoot 'research\clock_liveness.py'
if (-not (Test-Path $Organ)) { throw "clock_liveness.py missing at $Organ" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

# The interpreter DESK_HEALTH measures `py -3` resolving to (MT5-StateVector runs the same one).
$py = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $py)) { throw "python missing at $py" }
$log = Join-Path $DeskRoot 'logs\MT5-ClockLiveness.log'

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
    '/d /s /c cd /d "' + $DeskRoot + '" && "' + $py + '" -u -W ignore ' +
    'research\clock_liveness.py --once --budget-s 300 >> "' + $log + '" 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(28) `
             -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Forward-clock census: kept, retired, re-mint pending; repairs frozen clocks. Hourly." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} next=hourly :28 runs={2}" -f $t.TaskName, $t.State, $Organ
