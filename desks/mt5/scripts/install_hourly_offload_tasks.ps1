# Register the three hourly-cycle legs that get clocks of their own (2026-11-04):
#   MT5-OffloadForwardEnrolment  hourly at :35        PT10M   research
#   MT5-OffloadRecordTape        hourly at :45        PT20M   data
#   MT5-OffloadAllocatorHeavy    every 4 h from 00:40 PT45M   research
#
# WHY. The hourly pass is serial and its eleven ALWAYS_RUN legs cost 2,947 s against a 2,640 s
# rotation budget, so the rotating legs starve: the admission scan pf_allocator --mode heavy writes
# was 124 h old (cadence 3.5 h, consumer expiry 26 h) and forward_enrolment rarely ran. Each task
# runs desks/mt5/scripts/run_offload_leg.py, which calls exactly what hourly_cycle calls. See that
# file's docstring for the overlap rule: record_tape and forward_enrolment STAND BY (exit 0, receipt
# in desks/mt5/reports/offload/) until hourly_cycle.OWN_CLOCK_LEGS names them, because neither has
# a cross-process lock; the allocator runs at once, because all its clocks share one lock.
#
# TIMES ARE THE BOX'S CLOCK (UTC on vmi3571445). The heavy allocator pass is placed at 00:40,
# 04:40, 08:40, ... so none starts inside the 01:30-04:30Z money window. Tick capture runs every
# hour, as the cycle's own record_tape leg always has.
#
# SYSTEM, IgnoreNew, priority 7 (BELOW_NORMAL; the live E8 tasks run at 4), StartWhenAvailable.
# Each ExecutionTimeLimit sits ABOVE the runner's own child timeout, so the runner stops its child
# and writes its receipt rather than being killed holding it.
#
# Needs an elevated PowerShell (registering SYSTEM tasks). -DryRun prints and touches nothing.
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$repo = 'C:\opt\quant'
$desk = Join-Path $repo 'desks\mt5'
$logs = Join-Path $desk 'logs'
$runner = 'scripts\run_offload_leg.py'
$py = @((Join-Path $repo '.venv\Scripts\python.exe'),
        'C:\Program Files\Python314\python.exe',
        'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe') |
      Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { throw 'no python.exe found in .venv or either Python314 install' }
if ($py -like '*\AppData\*') { Write-Warning "using the per-user python ${py}: SYSTEM cannot see its user-site packages" }
if (-not (Test-Path (Join-Path $desk $runner))) { throw "missing $runner under $desk" }
Write-Output "python: $py"

$today = (Get-Date).Date
$jobs = @(
  @{ Name = 'MT5-OffloadForwardEnrolment'; Leg = 'forward_enrolment'
     Trigger = (New-ScheduledTaskTrigger -Once -At $today.AddMinutes(35) -RepetitionInterval (New-TimeSpan -Hours 1))
     Limit = (New-TimeSpan -Minutes 10) },
  @{ Name = 'MT5-OffloadRecordTape'; Leg = 'record_tape'
     Trigger = (New-ScheduledTaskTrigger -Once -At $today.AddMinutes(45) -RepetitionInterval (New-TimeSpan -Hours 1))
     Limit = (New-TimeSpan -Minutes 20) },
  @{ Name = 'MT5-OffloadAllocatorHeavy'; Leg = 'pf_allocator_heavy'
     Trigger = (New-ScheduledTaskTrigger -Once -At $today.AddMinutes(40) -RepetitionInterval (New-TimeSpan -Hours 4))
     Limit = (New-TimeSpan -Minutes 45) }
)

foreach ($j in $jobs) {
  $log = Join-Path $logs ("{0}.log" -f $j.Name)
  $cmd = "/d /s /c cd /d $desk && `"$py`" -u -W ignore $runner $($j.Leg) >> `"$log`" 2>&1"
  if ($DryRun) { Write-Output ("DRYRUN {0}: cmd.exe {1}" -f $j.Name, $cmd); continue }
  $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $cmd -WorkingDirectory $desk
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Priority 7 `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -ExecutionTimeLimit $j.Limit
  # Unregister first: -Force over an existing registration keeps stale settings on some builds.
  if (Get-ScheduledTask -TaskName $j.Name -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $j.Name -Confirm:$false
  }
  Register-ScheduledTask -TaskName $j.Name -Action $action -Trigger $j.Trigger `
    -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
  $t = Get-ScheduledTask -TaskName $j.Name
  Write-Output ("{0} registered: {1} priority={2} limit={3}" -f $j.Name, $t.State,
                $t.Settings.Priority, $t.Settings.ExecutionTimeLimit)
}
