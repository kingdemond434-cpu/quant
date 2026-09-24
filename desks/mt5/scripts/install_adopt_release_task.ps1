# REGISTER THE BOX'S PULL, AND RUN IT NOW (2026-09-08).
#
# THE GAP. Install-QuantWindows.ps1 registers MT5-AdoptRelease among ~twenty other tasks, and
# re-running the whole installer on a box whose tasks are live re-registers every one of them
# -- which on this box has already failed with "Access is denied" against the S4U principals.
# The adoption itself is one task and it is the ONLY thing standing between a day of fixes on
# origin and the gateway that runs them, so it gets the same single-task installer the moat
# miner and the contract terms got: idempotent, one file, no other task touched.
#
# WHAT IT DOES. Registers MT5-AdoptRelease -- hourly at :12, between the :05 and :20 ShadowSync
# slots (that task repeats every FIFTEEN minutes from :05 -- :05, :20, :35, :50 -- so the :20 this
# was first registered at was a sync slot, not a gap after one: two git writers in one repository
# in the same second, MEASURED 2026-09-08 from the two installers) and before the research legs
# at the top of the next hour read code -- pointing at Adopt-And-Seal.ps1, which lands the
# branch's tree in place (the box's own
# state kept), re-seals when HEAD is not the sealed code, commits RELEASE.json alone, and
# restarts MT5-Gateway on the new seal. Then STARTS it, so the first adoption happens now
# rather than at the next :20, and prints the task's state and last result so the run can be
# read from the same window that launched it.
#
# Mirrors the installer's block exactly (test_the_standalone_installer_agrees_with_the_full_one
# pins the two to each other): same name, same script, same cadence, same limits, same
# principal shape.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_adopt_release_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-AdoptRelease'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'scripts\Adopt-And-Seal.ps1'
if (-not (Test-Path $Script)) { throw "Adopt-And-Seal.ps1 missing at $Script" }

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument `
    ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`"" -f $Script)

# A DAILY trigger repeating hourly for one day, never a -Once trigger with a long duration.
# MEASURED 2026-09-22 on the trading box: the registered task carried
# `<Duration>P9DT2H40M</Duration><StopAtDurationEnd>true</StopAtDurationEnd>` -- the scheduler
# had folded the long duration into nine days -- so the repetition EXPIRED on 2026-09-21 02:52,
# `Next Run Time: N/A`, and nothing shipped after that ever reached the box. Daily-at-:12 with a
# one-day hourly repetition re-arms itself every midnight and has no end to expire.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(12))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(12)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# StartWhenAvailable so an hour missed to a reboot is caught up rather than silently skipped;
# IgnoreNew so a slow adoption is never stacked on itself.
#
# TWO HOURS, NOT TWENTY MINUTES, AND THE INSTALLER IS WHERE IT HAS TO SAY SO (2026-09-24).
# This line read `-Minutes 20` while both live boxes carried a limit the installer never wrote:
# the trading box PT2H (raised by hand when the adoption was repaired tonight) and the build box
# vmi3500897 PT50M. An installer that disagrees with every box it installed is not a declaration,
# it is a REGRESSION waiting for the next re-register -- re-running this file would have cut the
# repaired trading box from two hours back to twenty minutes and restored the exact outage:
#
#     ExecutionTimeLimit kills the run  -> LastTaskResult 267014 (0x41306, TASK_TERMINATED)
#     MultipleInstances IgnoreNew       -> the next hour is REFUSED, 0x800710E0, event 322
#
# Measured on vmi3500897 today: last run 2026-09-16 11:12, result 267014, 193 missed runs, 322
# commits behind origin. A cold adoption re-scans a ~24,000-path worktree per pathspec and waits
# on the git-writer mutex before it starts; it does not fit in twenty minutes and never did.
# The limit is a WATCHDOG, not a budget: it exists so a wedged run is eventually killed, and it
# has to sit above the slowest honest adoption or it only ever kills honest ones.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

# The same principal shape as MT5-ShadowSync, the task whose commits this one follows: the
# logged-on user, interactive, limited. Adoption writes files and runs git; it needs nothing
# more, and a task that asks for more than it needs is the one that fails to register.
# SYSTEM, ServiceAccount: the box's tasks run as SYSTEM (an Interactive principal only fires while
# that user holds a desktop session, and the adoption then dies with it).
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# RUNNING AS SYSTEM IS NOT ENOUGH; GIT HAS TO AGREE IT MAY READ THE REPOSITORY (2026-09-24).
# Measured on the build box vmi3500897 the first time this task ran as SYSTEM: every git call
# died instantly with
#
#     fatal: detected dubious ownership in repository at 'C:/opt/quant'
#     'C:/opt/quant' is owned by: VMI3500897/Administrator  but the current user is: NT AUTHORITY/SYSTEM
#
# and the run spent its whole window retrying `fetch` with backoff. Nothing in the task, the
# script or the branch was wrong -- git's ownership check was. The trading box never hit it
# because its repository is owned by BUILTIN\Administrators, of which SYSTEM is a member; the
# build box's is owned by the Administrator USER, of which SYSTEM is not.
#
# THE SYSTEM CONFIG, NOT --global. SYSTEM's HOME is C:\Windows\system32\config\systemprofile, so a
# `--global` exception written from an interactive session lands in the wrong file and the task
# still fails -- with the same message, which is what makes this worth the lines. `--system`
# covers every principal on the box, which is what "any scheduled task may adopt" actually means.
# Idempotent: the value is added only when it is not already there.
$repoForGit = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path -replace '\\', '/'
$already = @(git config --system --get-all safe.directory 2>$null)
if ($already -notcontains $repoForGit) {
    git config --system --add safe.directory $repoForGit 2>&1 | Out-Null
    "safe.directory: added {0} to the SYSTEM git config" -f $repoForGit
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Adopt the branch's code in place, re-seal the release, restart the gateway on the new seal." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

# THE FIRST ADOPTION IS NOW. Waiting for :12 is another hour of the gateway on the old tree.
# (Adopt-And-Seal itself waits out a ShadowSync pass that is still running, so starting inside
# one is safe.)
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"log: desks\mt5\logs\MT5-AdoptRelease.log is not written by the task itself; read the task history, or run Adopt-And-Seal.ps1 by hand to watch it."
