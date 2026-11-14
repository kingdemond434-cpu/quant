# REGISTER MT5-FTMO-Allocator -- THE FTMO BOOK'S SOLVE ON ITS OWN CLOCK (2026-11-05).
#
# THE GAP (measured on the box by Desk health, 2026-11-05 16:10Z). `prop_challenge_allocator` was
# a leg of MT5-HourlyCore, whose rotation admits a leg only while `spent + cost <= budget`. Its
# ~722 s never fit the room the always-run set leaves (2,640 s budget, ~2,000 s always-run), so it
# was "deferred, leads the next pass" every pass and NEVER RAN after 2026-10-29 15:39Z. It is the
# only writer of FTMO's live book (the CERT_BOOK_LIVE `ftmo` block), so for seven days FTMO traded
# only the gold fallback. A money-path writer must not depend on the hourly window at all.
#
# WHAT IT DOES. Every hour at :50 box-local (clear of the :05/:12/:20 repository-writer slots and of
# HourlyCore's :36 start), `research\prop_challenge_allocator.py` as SYSTEM, below-normal priority.
# The leg is in `hourly_cycle.OWN_CLOCK_LEGS`, so no cycle plan runs it too (no double write), and
# `scripts/check_own_clock_legs.py` fails if this task is missing. The script itself writes
# reports\FTMO_ALLOCATOR.json and the gap hypotheses always, and the CERT_BOOK_LIVE `ftmo` block
# ONLY when data\FTMO_ALLOCATOR_ARMED exists -- registering this task arms nothing.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists -- the form
# Adopt-And-Seal.ps1 calls on every adoption. Without it, the registration is replaced.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_ftmo_allocator_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_ftmo_allocator_task.ps1 -IfMissing
param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-FTMO-Allocator'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'research\prop_challenge_allocator.py'
$Log      = Join-Path $DeskRoot 'logs\MT5-FTMO-Allocator.log'
$py       = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Script)) { throw "prop_challenge_allocator.py missing at $Script" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
    '/d /s /c cd /d "' + $DeskRoot + '" && "' + $py + '" -u -W ignore "' + $Script + '" ' +
    '>> "' + $Log + '" 2>&1') -WorkingDirectory $DeskRoot

# A DAILY trigger repeating hourly for one day re-arms itself at midnight and never expires
# (a -Once trigger with a long duration expired on this box on 2026-09-21).
$start = (Get-Date).Date.AddMinutes(50)
$trigger = New-ScheduledTaskTrigger -Daily -At $start
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# FORTY MINUTES is a watchdog, not a budget: ~722 s measured under HourlyCore's contention.
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -Priority 7

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
    'DRYRUN would register {0}: hourly at :50, SYSTEM, PT40M, priority 7, runs {1}' -f $TaskName, $Script
    exit 0
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "FTMO book solve (prop_challenge_allocator), hourly; CERT_BOOK_LIVE ftmo block only when FTMO_ALLOCATOR_ARMED exists." | Out-Null
$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} next=hourly :50 runs={2}" -f $t.TaskName, $t.State, $Script
