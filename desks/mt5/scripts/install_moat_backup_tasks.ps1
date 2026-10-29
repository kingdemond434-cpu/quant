# Register MT5-MoatBackup (daily) and MT5-RestoreDrill (weekly) on the trading box.
#
# THE MOAT BACKUP WAS ON A CLOCK ONLY ON A MACHINE THAT IS GONE (measured 2026-10-29). Both
# organs were scheduled as Linux systemd timers on the old VPS (ops/quant-moat-backup.timer,
# ops/quant-restore-drill.timer, ops/crontab.manifest) and never as Windows tasks here. So the
# replica in backups/moat/ is the VPS's last one (manifest "generated" 2026-08-29), BACKUP_STATE
# reads "no moat backup manifest on this host", and the 10-27 restore drill FAILED against that
# two-month-old replica (forward evidence restored below 90% of the live rows).
#
# WHAT EACH ONE DOES. scripts/run_moat_backup.py replicates the small irreplaceable stores
# (execution tape, alpha registry, capital events, sleeve registry, shadow state and ledgers,
# universal survivors) into backups/moat/ with a sha256 manifest, and restore-drills every replica
# on every run; backups/ is not gitignored, so the daily git snapshot carries it to GitHub. Free,
# a second machine, a different failure domain. scripts/run_restore_drill.py restores the forward
# evidence from that replica into a temp directory, parses it as its readers do, and fails below
# 90% of the live row counts. Neither writes to a live path; neither reads data/secrets.
#
# OUTSIDE THE MONEY WINDOW, NOT THE VPS'S HOURS. Times are the box's own clock, which is UTC on
# vmi3571445. The VPS ran the backup at 03:55, which here lands inside the gold Asia placements
# (E8 ~04:01Z, Fusion and FTMO ~04:16-04:24Z) and the 01:30-04:30Z money-path quiet window, so an
# IO burst could delay an order. Backup 06:40 daily; drill Sunday 07:20, after that day's backup.
# BelowNormal priority and IgnoreNew so neither can stack or starve the gateway.
#
# LAST RESULT 0x2 IS A VERDICT, NOT A BROKEN TASK. run_moat_backup.py exits 2 on DEGRADED,
# DRILL-FAILED, DISK-FUSE and NOTHING-REPLICATED, and run_restore_drill.py exits 1 on FAIL, on
# purpose: the scheduler's Last Result is then the alarm. Do not "fix" it to 0.
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'
$repo = 'C:\opt\quant'
$logs = Join-Path $repo 'desks\mt5\logs'
# The interpreter the box actually has: the repo venv first, then the two installs the other
# task installers name (they disagree, so this one looks instead of guessing).
$py = @((Join-Path $repo '.venv\Scripts\python.exe'),
        'C:\Program Files\Python314\python.exe',
        'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe') |
      Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { throw 'no python.exe found in .venv or either Python314 install' }
# SYSTEM can run a per-user install but does not see that user's site-packages.
if ($py -like '*\AppData\*') { Write-Warning "using the per-user python $py: SYSTEM cannot see its user-site packages" }
Write-Output "python: $py"

$jobs = @(
  @{ Name = 'MT5-MoatBackup'; Script = 'scripts\run_moat_backup.py'
     Trigger = (New-ScheduledTaskTrigger -Daily -At '06:40')
     Limit = (New-TimeSpan -Hours 1) },
  @{ Name = 'MT5-RestoreDrill'; Script = 'scripts\run_restore_drill.py'
     Trigger = (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '07:20')
     Limit = (New-TimeSpan -Minutes 30) }
)

foreach ($j in $jobs) {
  if (-not (Test-Path (Join-Path $repo $j.Script))) { throw "missing $($j.Script) under $repo" }
  $log = Join-Path $logs ("{0}.log" -f $j.Name)
  $cmd = "/d /s /c cd /d $repo && `"$py`" -u -W ignore $($j.Script) >> `"$log`" 2>&1"
  if ($DryRun) { Write-Output ("DRYRUN {0}: cmd.exe {1}" -f $j.Name, $cmd); continue }
  $action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $cmd -WorkingDirectory $repo
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Priority 7 `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -ExecutionTimeLimit $j.Limit
  Register-ScheduledTask -TaskName $j.Name -Action $action -Trigger $j.Trigger `
    -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null
  $t = Get-ScheduledTask -TaskName $j.Name
  Write-Output ("{0} registered: {1} priority={2}" -f $j.Name, $t.State, $t.Settings.Priority)
}
