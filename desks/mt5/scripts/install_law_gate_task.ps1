<#
  MT5-LawGate -- THE LAW BATTERY, ON A CLOCK THAT COMPLETES.

  WHY THIS EXISTS. `data/law_gate.json` on this box was 270 HOURS old and held 14 of 56 fences,
  so `check_fences_ran` reported forty fences as never run and, by the desk's own L1.49, every
  green claim resting on them was uncashable. The battery was not disabled and nothing had
  failed: `full_gate` gives each of 56 fences up to 600 s, which is up to nine hours, and no
  hourly window can hold that. A gate that cannot fit its window does not run at all.

  WHAT THIS REGISTERS. `run_law_gate.py --rotate` runs the fences that have gone longest without
  a verdict until its budget is spent and MERGES them into the record, which carries `ran_at`
  per fence and the window it must be inside. Measured on the first pass: 18 fences in 120 s, so
  a 30-minute hourly budget covers the whole battery several times inside the 48 h window.

  It never disables a fence and never lowers a bar: a fence that stops running falls out of the
  record inside the window and is reported as never run, which is the measurement.
#>
$ErrorActionPreference = 'Stop'
$TaskName = 'MT5-LawGate'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "python not on PATH" }
$action = New-ScheduledTaskAction -Execute $python `
    -Argument 'scripts\run_law_gate.py --rotate --budget-s 1800' -WorkingDirectory $RepoRoot
# :40 past the hour: clear of the :05/:12/:20 git-writer slots, so a fence never waits on a lock.
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(40)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Law battery in rotation: oldest fences first, merged into data/law_gate.json with each fence's own hour." | Out-Null
Write-Host ("  [OK  ] {0} registered (hourly at :40, 1800 s of fences per pass)" -f $TaskName)
