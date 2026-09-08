<#
.SYNOPSIS
    Register the MT5 desk's scheduled work on THIS Windows box, deriving every
    path instead of carrying another machine's.

.DESCRIPTION
    WHY THE EXISTING SCRIPTS COULD NOT BE COPIED ACROSS

    MT5Hourly.cmd and MT5Sync.cmd hardcode `C:\Users\dell\mt5-research` and a
    specific Python 3.12 install path. On any other box every one of those is
    wrong, and the failure is quiet in the worst way: `cd /d` to a missing
    directory does NOT stop a .cmd file, so the loop runs `research\hourly_cycle.py`
    from whatever directory it happened to start in, fails, and keeps looping
    forever at one attempt per hour with nothing reporting it.

    This derives the checkout from its own location and finds the interpreter,
    so there is nothing to edit when the box changes.

    WHY TASK SCHEDULER AND NOT THE .cmd LOOPS

    The old pattern is `:loop / run / timeout 3540 / goto loop` started from the
    Startup folder. It has three holes this closes:

      - Nothing restarts it. If the cmd window is closed, the process is killed,
        or the box reboots without a logon, the loop is simply gone. Task
        Scheduler restarts a failed task and runs AtStartup, not just at logon.
      - `timeout` is not a schedule. A run that takes 20 minutes makes the next
        one 80 minutes late, and the drift accumulates silently.
      - No record. A .cmd loop that has been dead for a week looks identical to
        one that is running and finding nothing to do.

    WHAT IT DOES NOT DO

    It does not start MT5, and it does not arm trading. The gateway task moves
    orders only when the gateway itself decides to; registering a schedule is
    not the same act as arming a book, and this script deliberately cannot do
    the second one.

.PARAMETER DeskRoot
    The desks/mt5 checkout. Defaults to this script's parent, correct by
    construction.

.PARAMETER Python
    Interpreter to run the desk with. Defaults to the repo venv if present,
    then `py -3`. NEVER `python3` -- that name is Linux-only and does not exist
    on Windows, which is the single most common failure when following a
    runbook written on Linux.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\Install-QuantWindows.ps1
#>
[CmdletBinding()]
param(
    [string] $DeskRoot,
    [string] $Python,
    [string] $AurumRoot,
    [switch] $WhatIfOnly
)

$ErrorActionPreference = "Stop"

if ($PSVersionTable.PSVersion.Major -lt 3) {
    Write-Host "FATAL: PowerShell $($PSVersionTable.PSVersion); need 3.0+."
    exit 1
}

# $PSScriptRoot is unreliable inside a param() default on 5.1 -- resolved here.
if (-not $DeskRoot) {
    $d = $PSScriptRoot
    if (-not $d) { $d = Split-Path -Parent $MyInvocation.MyCommand.Path }
    if (-not $d) { throw "cannot locate this script; pass -DeskRoot explicitly" }
    $DeskRoot = Split-Path -Parent $d
}
$DeskRoot = (Resolve-Path $DeskRoot).Path

if (-not (Test-Path (Join-Path $DeskRoot "research\hourly_cycle.py"))) {
    Write-Host "FATAL: no research\hourly_cycle.py under $DeskRoot."
    Write-Host "       That is not the desks/mt5 checkout. Pass -DeskRoot."
    exit 1
}

if (-not $Python) {
    $venv = Join-Path $DeskRoot "..\..\.venv\Scripts\python.exe"
    if (Test-Path $venv) { $Python = (Resolve-Path $venv).Path }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = "py" }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $Python = "python" }
    else {
        Write-Host "FATAL: no interpreter. Install Python 3.12+, or create the"
        Write-Host "       repo venv:  py -3 -m venv .venv"
        Write-Host "       NOTE: 'python3' is a Linux name and never exists here."
        exit 1
    }
}
$pyArgs = if ($Python -eq "py") { "-3 " } else { "" }

Write-Host ""
Write-Host ("=" * 74)
Write-Host "QUANT MT5 DESK -- Windows scheduled work"
Write-Host ("=" * 74)
Write-Host "  checkout    $DeskRoot"
Write-Host "  interpreter $Python"

# Logs must exist before a task writes to them; a task that fails on a missing
# directory reports "last result 0x1" and nothing about the reason.
$logDir = Join-Path $DeskRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

#: REPETITION DURATION IS 10 YEARS, NOT [TimeSpan]::MaxValue. MaxValue
#: serialises to the ISO-8601 duration P99999999DT23H59M59S, which the Task
#: Scheduler service rejects outright:
#:
#:   Register-ScheduledTask : The task XML contains a value which is
#:   incorrectly formatted or out of range. (8,42):Duration:P99999999DT23H59M59S
#:
#: It fails at REGISTRATION, so the task simply does not exist afterwards --
#: and a script that reports the other tasks fine leaves an operator believing
#: the schedule is installed. 3650 days is indefinite for any practical purpose
#: and serialises to a duration the service accepts.
#:
#: name -> (script, schedule-builder, description)
#: The gateway runs EVERY MINUTE and holds its own file lock, so overlapping
#: passes cannot double-bracket. The hourly cycle self-guards on a UTC date
#: stamp, so running it hourly gives exactly one daily-cycle run per day and
#: catches up whenever the box is awake instead of missing a fixed minute.
$tasks = @(
    @{ Name = "MT5-Gateway"
       Script = "research\run_gateway_loop.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "One gateway pass per minute; file-locked against overlap." },
    @{ Name = "MT5-Hourly"
       Script = "research\hourly_cycle.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "Health, mining, and the daily chain: shadow -> promoter -> markout -> export." },
    @{ Name = "MT5-AllocatorFast"
       Script = "research\\pf_allocator.py"
       Args = "--mode fast"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 5) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # THE ALLOCATOR'S OWN FAST CLOCK, which its docstring names and nothing ever ran.
       # `--mode fast` reuses the cached scenario population and re-solves the book in ~5 min,
       # so the per-sleeve growth-maximising fractions track the account between hourly passes.
       # `decision_core._ALLOC_MAX_AGE_S` is 3600, so without a sub-hourly clock the book spends
       # most of every hour close to expiry; with one it is always fresh. The file holds a single
       # job lock across all three modes, so a fast pass that collides with the hourly `normal`
       # one waits instead of thrashing beside it.
       Desc = "E[log W] per-sleeve heat, fast clock: re-solve the book every 5 minutes." },
    @{ Name = "MT5-NewsDesk"
       Script = "research\\news_desk.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 5) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # THE NEWS LANE, WHICH RAN ON NO CLOCK AT ALL. Measured 2026-09-07: news_desk.py,
       # earnings_miner.py, delayed_reaction_miner.py, failed_reaction_miner.py and
       # operational_calendar_miner.py appear in neither cycle and in no task. Under the
       # principal's two-lane mandate (2026-09-06) single-name equities are traded on news,
       # earnings and financial reports and are never hunted for statistical hypotheses -- so
       # with this lane unscheduled, that entire half of the universe had no path to a trade.
       # Five minutes because a reaction edge decays in minutes; an hourly news desk is a
       # history desk.
       Desc = "News, earnings and event reaction: the equity lane's own clock." },
    @{ Name = "MT5-Shadow"
       Script = "research\shadow_cycle.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 15) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "Refresh broker bars and replay every configured zero-capital sleeve every 15m." },
    # ---- THE SIX THIS INSTALLER NEVER REGISTERED --------------------------------------------
    # `ops/reboot_drill.ps1` has always REQUIRED eleven tasks and this table only ever built
    # five, so a rebuilt box passed the installer and then failed its own drill. Worse, the
    # tasks it did not build are the ones nobody notices missing: the publisher, the watchdog
    # and the gauntlet all fail SILENTLY -- the desk keeps computing and simply stops being
    # seen, judged or healed. Measured 2026-09-07: data\stall_watch.json last written
    # 2026-09-06T23:57, thirteen hours before the box was next looked at.
    @{ Name = "MT5-DeskState"
       Script = "scripts\\build_zentech_state.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 5) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # FIVE MINUTES BECAUSE THE DRILL ITSELF SETS THE BOUND: reboot_drill fails the box when
       # desk_state's account read is over 900s old, so any slower clock guarantees a FAIL that
       # says "terminal is up but not feeding" when nothing is wrong except this cadence.
       Desc = "Rebuild web/desk_state.json -- the file every dashboard reads." },
    @{ Name = "MT5-Gauntlet"
       Script = "scripts\\external_gauntlet.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # The ten gates. Also a leg of the hourly cycle, and deliberately BOTH: the cycle can be
       # long, and a judged docket is what every downstream stage waits on. Its own job lock
       # makes the overlap a wait, not a race.
       Desc = "The ten statistical gates, hourly, over every newly backtested cell." },
    @{ Name = "MT5-Frontier"
       Script = "frontier_intel\\frontier_supervisor.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # THE INSTITUTIONAL FRONTIER MINER, on its own clock rather than only inside the hourly
       # cycle: its whole purpose is to keep closing the gap to the best publicly observable
       # research organisations, and an organ that only runs when a 55-leg cycle reaches leg 48
       # is an organ that stops the first time an earlier leg is slow.
       Desc = "Frontier gap scan: what elite public research orgs do that this desk does not." },
    @{ Name = "MT5-ResearchReports"
       Script = "scripts\\run_research_reports.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # ELEVEN PRODUCERS DECLARE AN HOURLY CADENCE AND ARE REACHABLE ONLY AS LEGS OF A 55-LEG
       # CYCLE THAT NOW EXCEEDS AN HOUR. `issue_board` is itself a leg of that cycle and runs
       # BEFORE the four research reports it measures, so at measurement time their artifacts
       # were written by the PREVIOUS pass -- their age is one full cycle duration. Past
       # STALE_TOLERANCE (2.0) the board reports them STALLED on every pass, forever, while the
       # producers run perfectly well. Measured 2026-09-07: issue_board last wrote 12:37 and had
       # not run again by 13:49.
       #
       # The fix is a clock, not a looser threshold: raising the tolerance would silence the
       # symptom and leave the artifacts exactly as old. This refreshes only what is past half
       # its cadence, under a per-producer lock, so on a healthy box it is one stat() apiece.
       Desc = "Give every hourly producer its own clock, independent of the long cycle." },
    @{ Name = "MT5-MoatSilver"
       Script = "moat\\moat_silver.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "Bronze tick tape -> the parquet the tape-input families actually read." },
    @{ Name = "MT5-MoatRecorder"
       Script = "moat\\moat_recorder.py"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 10) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       # A RESIDENT LOOP ON A TEN-MINUTE TRIGGER, which is not a contradiction: the recorder
       # holds a single-instance lock, so a trigger that fires while it is running exits
       # immediately and a trigger that fires after a crash restarts it. That is the cheapest
       # correct watchdog for a process whose failure mode is "died quietly at 02:00".
       TimeLimit = (New-TimeSpan -Days 3650)
       Desc = "The permanent Fusion tick tape -- restarts itself within 10 minutes of any death." },
    # ---- THE DAILY CYCLE, TWO LANES TWELVE HOURS APART --------------------------------------
    # Both execute docs\DESK_CYCLE_PROMPT.md; the lane decides which half they own. The split is
    # what stops two agents editing the same files twelve hours apart and calling it progress:
    # NOON owns conversion and research throughput, MIDNIGHT owns wiring, cadence and repair.
    #
    # DAILY AT A FIXED HOUR, not a repetition interval like every other task here. These are long
    # passes whose value is in being ONE considered sweep rather than a poll, and a repetition
    # trigger would stack a second agent on top of a first that had not finished.
    #
    # The launcher exits NON-ZERO when its CLI is absent, deliberately -- so a box without the
    # agent installed shows a failing task rather than a green one that does nothing. That is the
    # MT5-ShadowSync defect (exit 0 while publishing nothing for 33 hours) refused by design.
    # HOURLY REPETITION ON TOP OF THE DAILY START, which is what makes an interrupted pass resume
    # "right after it is back" instead of at the next daily slot. The launcher keeps a checkpoint:
    # a firing that finds today's lane DONE costs one file read and exits, one that finds it
    # RUNNING with a dead process resumes it with the finished stages named, one that finds
    # nothing starts fresh. So the recovery window after a time-limit kill or a reboot is an hour,
    # not a day -- and a healthy box pays eleven cheap no-ops for that.
    @{ Name = "MT5-CycleNoon"
       Kind = "ps1"
       Script = "scripts\\Run-DeskCycle.ps1"
       Args = "-Lane noon"
       Trigger = { New-ScheduledTaskTrigger -Daily -At "12:00" `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Hours 11) }
       # ELEVEN HOURS, not twelve: the repetition must stop before the OTHER lane's daily start,
       # or noon would still be waking up while midnight begins and the lane split -- the whole
       # reason two agents can share this repository -- would be gone.
       TimeLimit = (New-TimeSpan -Hours 10)
       Desc = "Daily conversion pass: force the funnel, clock every certificate, chase miner yield." },
    @{ Name = "MT5-CycleMidnight"
       Kind = "ps1"
       Script = "scripts\\Run-DeskCycle.ps1"
       Args = "-Lane midnight"
       Trigger = { New-ScheduledTaskTrigger -Daily -At "00:00" `
                     -RepetitionInterval (New-TimeSpan -Hours 1) `
                     -RepetitionDuration (New-TimeSpan -Hours 11) }
       TimeLimit = (New-TimeSpan -Hours 10)
       Desc = "Daily wiring pass: schedule the unwired, repair staleness and failing tasks." },
    @{ Name = "MT5-StallWatch"
       Kind = "ps1"
       Script = "scripts\\stall_watch.ps1"
       Trigger = { New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                     -RepetitionInterval (New-TimeSpan -Minutes 10) `
                     -RepetitionDuration (New-TimeSpan -Days 3650) }
       Desc = "Heal stacked, stalled and Disabled research tasks; never touches the money path." }
)

# NOT IN THIS TABLE, AND THE REASONS ARE NOT SYMMETRIC:
#   MT5-ShadowSync    already has its own registration block further down, and that block is
#                     strictly better than a table row: it offsets the trigger five minutes past
#                     the 00/15/30/45 replay slots so the publisher never races a ledger write,
#                     and sets -MultipleInstances IgnoreNew. A table row would fire exactly ON
#                     those slots -- the race its own comment exists to avoid -- and, registering
#                     first, would simply be replaced by the block a moment later. Two
#                     registrations of one task is not redundancy, it is a coin toss about which
#                     settings survive.
#   MT5-TerminalBoot  starts terminal64.exe, which is a GUI process. A task registered here runs
#                     in the same session as the rest, but the terminal needs an INTERACTIVE
#                     logon; ops/box-repair.ps1 documents the fix (schtasks /Change /RU <user>
#                     /IT, elevated). Registering it from this table would create a task that
#                     reports success and never produces a terminal, which is worse than absent.
#   MT5-Universe      names no script in this checkout. Registering a guess would satisfy the
#                     reboot drill's name check while running nothing -- the exact "capability
#                     that is code, not a capability" failure the desk keeps paying for.
# Both are reported by the drill as MISSING, which is the honest state until each is resolved.

# TWO ROOTS, EXACTLY AS `hourly_cycle._producer` RESOLVES THEM. The research organs live under
# `desks/mt5/...`, but the publication and maintenance scripts live at the REPOSITORY root --
# `scripts\build_zentech_state.py` is the dashboard builder and it is not under the desk. With a
# single root the loop below finds nothing, prints `[SKIP]`, and the installer exits reporting
# success on a box that has no dashboard publisher: the drill then fails with MT5-DeskState
# MISSING and the cause is one Join-Path away from where anyone looks.
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot "..\..")).Path

foreach ($t in $tasks) {
    $script = $null
    foreach ($root in @($DeskRoot, $RepoRoot)) {
        $cand = Join-Path $root $t.Script
        if (Test-Path $cand) { $script = $cand; break }
    }
    if (-not $script) {
        Write-Host ("  [SKIP] {0,-14} {1} found under neither {2} nor {3}" -f `
                    $t.Name, $t.Script, $DeskRoot, $RepoRoot)
        continue
    }
    $log = Join-Path $logDir ("{0}.log" -f $t.Name)
    # cmd /c wraps the redirect: Task Scheduler has no shell, so `>>` in the
    # arguments field is passed to python as a literal argument otherwise.
    # cmd.exe needs an OUTER quote pair when the executable itself is quoted. Without it,
    # Task Scheduler returns 1 before Python starts and no log is created.
    # SCRIPT ARGUMENTS, so a task can name WHICH mode it runs. pf_allocator has three clocks
    # (`fast` ~5 min, `normal` hourly, `heavy` overnight) selected by --mode, and without an
    # argument slot here the table could only ever register its default. Absent Args is "".
    $targs = if ($t.ContainsKey("Args") -and $t.Args) { " " + $t.Args } else { "" }
    # KIND, because two of this desk's most important periodic jobs are PowerShell and not
    # Python: the 15-minute publisher and the stall watchdog. Running a .ps1 through $Python
    # does not fail loudly -- Python reports a SyntaxError into the log and the task records
    # result 1, which reads exactly like a script that ran and found a problem. So the
    # interpreter is chosen from the task, and the default stays Python.
    $kind = if ($t.ContainsKey("Kind") -and $t.Kind) { $t.Kind } else { "py" }
    if ($kind -eq "ps1") {
        # -NonInteractive and -NoProfile so a profile that prompts, writes, or fails cannot
        # hang or contaminate a task that nobody is watching. ExecutionPolicy Bypass is scoped
        # to this one process and changes no machine policy.
        $cmd = "/d /s /c `"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"$targs >> `"$log`" 2>&1`""
    } else {
        $cmd = "/d /s /c `"`"$Python`" $pyArgs`"$script`"$targs >> `"$log`" 2>&1`""
    }

    if ($WhatIfOnly) {
        Write-Host ("  [DRY ] {0,-14} cmd {1}" -f $t.Name, $cmd)
        continue
    }

    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd `
                                      -WorkingDirectory $DeskRoot
    # RestartCount/RestartInterval are what replace systemd's Restart=always.
    # StartWhenAvailable catches up a run missed while the box was off, which is
    # the whole point on a machine that is not guaranteed up.
    # FOUR HOURS IS A CEILING FOR A PASS, NOT FOR A RESIDENT LOOP. The tick recorder is meant to
    # stay up; killing it every four hours would punch a four-hourly hole in the one dataset on
    # this desk that cannot be re-obtained. A task that declares TimeLimit overrides the default.
    $limit = if ($t.ContainsKey("TimeLimit") -and $t.TimeLimit) { $t.TimeLimit } else { New-TimeSpan -Hours 4 }
    # IgnoreNew: A REPETITION INTERVAL PLUS A SLOW PASS IS A STACK. The cycle lanes repeat hourly
    # so an interrupted pass resumes quickly, and a pass that is simply still working must not
    # have a second copy started on top of it -- two agents in one repository is the collision the
    # lane split exists to prevent. The launcher checks its own checkpoint as well, because a
    # scheduler setting is not a guarantee anyone can read from the script.
    # StartWhenAvailable is what catches up a trigger missed while the box was off.
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit $limit

    try {
        Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
            -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask -TaskName $t.Name -Action $action `
            -Trigger (& $t.Trigger) -Settings $settings `
            -Description $t.Desc -Principal $principal | Out-Null
        Write-Host ("  [OK  ] {0,-14} registered -> {1}" -f $t.Name, $log)
    } catch {
        Write-Host ("  [FAIL] {0,-14} {1}" -f $t.Name, $_.Exception.Message)
    }
}

# The research supervisor is a persistent queue/experiment worker, not a one-shot task. A short
# recurring trigger supplies crash recovery; IgnoreNew keeps exactly one live owner.
$supervisor = Join-Path $DeskRoot "research\research_supervisor.py"
if (Test-Path $supervisor) {
    if ($WhatIfOnly) {
        Write-Host "  [DRY ] MT5-ResearchSupervisor persistent canonical worker"
    } else {
        try {
            # Use base pythonw directly: no console and no short-lived venv launcher parent for
            # Task Scheduler to mistake for the persistent worker.
            $basePython = (& $Python -c "import sys; print(sys._base_executable)").Trim()
            $supervisorPython = Join-Path (Split-Path $basePython) "pythonw.exe"
            if (-not (Test-Path $supervisorPython)) { $supervisorPython = $basePython }
            $supAction = New-ScheduledTaskAction -Execute $supervisorPython `
                -Argument ("`"{0}`"" -f $supervisor) -WorkingDirectory $DeskRoot
            $supTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
                -RepetitionInterval (New-TimeSpan -Minutes 5) `
                -RepetitionDuration (New-TimeSpan -Days 3650)
            $supSettings = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                -ExecutionTimeLimit (New-TimeSpan -Hours 72) -MultipleInstances IgnoreNew
            $supPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
                -LogonType Interactive -RunLevel Limited
            Unregister-ScheduledTask -TaskName "MT5-ResearchSupervisor" `
                -Confirm:$false -ErrorAction SilentlyContinue
            Register-ScheduledTask -TaskName "MT5-ResearchSupervisor" -Action $supAction `
                -Trigger $supTrigger -Settings $supSettings -Principal $supPrincipal `
                -Description "Persistent canonical MT5 hypothesis/research worker." | Out-Null
            Write-Host "  [OK  ] MT5-ResearchSupervisor registered"
        } catch {
            Write-Host ("  [FAIL] MT5-ResearchSupervisor {0}" -f $_.Exception.Message)
        }
    }
}

$shadowSync = Join-Path $DeskRoot "scripts\sync_shadow_to_git.ps1"
if ((Test-Path $shadowSync) -and -not $WhatIfOnly) {
    try {
        $syncAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
            ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`"" -f $shadowSync)
        # Five minutes after the 00/15/30/45 replay slots: never race a ledger write.
        $syncTrigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(5)) `
            -RepetitionInterval (New-TimeSpan -Minutes 15) `
            -RepetitionDuration (New-TimeSpan -Days 3650)
        $syncSettings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
        $syncPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
            -LogonType Interactive -RunLevel Limited
        Unregister-ScheduledTask -TaskName "MT5-ShadowSync" `
            -Confirm:$false -ErrorAction SilentlyContinue
        Register-ScheduledTask -TaskName "MT5-ShadowSync" -Action $syncAction `
            -Trigger $syncTrigger -Settings $syncSettings -Principal $syncPrincipal `
            -Description "Commit MT5 shadow-health state to git for cross-brain visibility." | Out-Null
        Write-Host "  [OK  ] MT5-ShadowSync registered"
    } catch {
        Write-Host ("  [FAIL] MT5-ShadowSync {0}" -f $_.Exception.Message)
    }
} elseif ($WhatIfOnly) {
    Write-Host "  [DRY ] MT5-ShadowSync 15-minute artifact publisher"
}

# MT5-AdoptRelease: the box PULLS. Until 2026-09-08 this box only ever pushed its state to the
# branch and never took anything back, so every fix landed on origin and stayed there while the
# gateway ran a tree that could not import `libs` and refused new risk on a stale seal for a
# full day. Adopt-And-Seal.ps1 lands the branch's tree in place (Adopt-Release.ps1 -- survives a
# locked or NTFS-damaged path), re-seals only when HEAD is not already the sealed code, commits
# RELEASE.json alone, and restarts the gateway so the new seal is read. Twelve past the hour:
# between the :05 and :20 ShadowSync slots -- that task repeats every FIFTEEN minutes from :05
# (:05, :20, :35, :50), so the :20 this was first registered at was itself a sync slot and put
# two git writers in one repository in the same second (MEASURED 2026-09-08) -- and before the
# research legs at the top of the next hour read code. Adopt-And-Seal also waits out a sync pass
# that is still running, and the sync yields to a running adoption.
$adoptSeal = Join-Path $DeskRoot "scripts\Adopt-And-Seal.ps1"
if ((Test-Path $adoptSeal) -and -not $WhatIfOnly) {
    try {
        $adoptAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
            ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`"" -f $adoptSeal)
        $adoptTrigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(12)) `
            -RepetitionInterval (New-TimeSpan -Hours 1) `
            -RepetitionDuration (New-TimeSpan -Days 3650)
        $adoptSettings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
            -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
        $adoptPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
            -LogonType Interactive -RunLevel Limited
        Unregister-ScheduledTask -TaskName "MT5-AdoptRelease" `
            -Confirm:$false -ErrorAction SilentlyContinue
        Register-ScheduledTask -TaskName "MT5-AdoptRelease" -Action $adoptAction `
            -Trigger $adoptTrigger -Settings $adoptSettings -Principal $adoptPrincipal `
            -Description "Adopt the branch's code in place, re-seal the release, restart the gateway on the new seal." | Out-Null
        Write-Host "  [OK  ] MT5-AdoptRelease registered (hourly at :12)"
    } catch {
        Write-Host ("  [FAIL] MT5-AdoptRelease {0}" -f $_.Exception.Message)
    }
} elseif ($WhatIfOnly) {
    Write-Host "  [DRY ] MT5-AdoptRelease hourly adopt + re-seal"
}

# MT5-ArtifactSync (sync_to_vps.ps1) is UNWIRED, not deleted (2026-08-23): its whole job was
# scp'ing to Hetzner (95.216.191.70), which is now fully decommissioned. There is no destination
# left, so registering this task would just fail every hour forever. Ensure it is NOT registered
# -- unregistering on every install run makes this durable even if a prior run (or a stale task
# from before this fix) left it behind, unlike a one-off manual Unregister-ScheduledTask.
# sync_to_vps.ps1 itself is untouched in case a VPS destination is ever needed again.
if (-not $WhatIfOnly) {
    Unregister-ScheduledTask -TaskName "MT5-ArtifactSync" -Confirm:$false -ErrorAction SilentlyContinue
}
Write-Host "  [OK  ] MT5-ArtifactSync intentionally not registered (Hetzner decommissioned)"

# L1.67 FENCE, WIRED, NOT JUST WRITTEN. scripts/check_risk_units.py exists, is correct, and
# CAUGHT NOTHING for its entire life because nothing ever ran it -- the exact bug it exists to
# catch (gateway.py silently reverted to gold's flat sizing constants, 5.9x over-risk on a
# promoted non-gold sleeve) shipped and sat undetected in a same-night regression until a broken
# TEST COLLECTION forced a manual trace. The desk's own enforcement matrix (build_enforcement_
# matrix.py) counts a fence as "ENFORCED" the moment the file exists, and cannot see the
# difference between that and a fence that actually runs -- this is what closes that gap for L1.67
# specifically. Daily cadence: sizing correctness does not drift minute to minute, and the fence's
# own universe-snapshot staleness check already tolerates up to 30 days.
$fenceQuantRoot = Split-Path -Parent (Split-Path -Parent $DeskRoot)
$riskUnitsFence = Join-Path $fenceQuantRoot "scripts\check_risk_units.py"
if (Test-Path $riskUnitsFence) {
    if ($WhatIfOnly) {
        Write-Host "  [DRY ] MT5-RiskUnitsFence daily L1.67 sizing-path audit"
    } else {
        try {
            # cmd /c wraps the redirect: Task Scheduler has no shell, so `>>` passed directly
            # in a Python argument string is taken as a literal argument, not a redirect --
            # same fix as the main $tasks loop above, for the same reason.
            $fenceLog = Join-Path $logDir "MT5-RiskUnitsFence.log"
            $fenceCmd = "/d /s /c `"`"$Python`" $pyArgs`"$riskUnitsFence`" >> `"$fenceLog`" 2>&1`""
            $fenceAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $fenceCmd `
                -WorkingDirectory $fenceQuantRoot
            $fenceTrigger = New-ScheduledTaskTrigger -Daily -At "06:20"
            $fenceSettings = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
            $fencePrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
                -LogonType Interactive -RunLevel Limited
            Unregister-ScheduledTask -TaskName "MT5-RiskUnitsFence" `
                -Confirm:$false -ErrorAction SilentlyContinue
            Register-ScheduledTask -TaskName "MT5-RiskUnitsFence" -Action $fenceAction `
                -Trigger $fenceTrigger -Settings $fenceSettings -Principal $fencePrincipal `
                -Description "L1.67 daily fence: no sizing call site may price a stop from another instrument's constants." | Out-Null
            Write-Host "  [OK  ] MT5-RiskUnitsFence registered"
        } catch {
            Write-Host ("  [FAIL] MT5-RiskUnitsFence {0}" -f $_.Exception.Message)
        }
    }
} else {
    Write-Host "  [SKIP] MT5-RiskUnitsFence scripts\check_risk_units.py not found at repo root"
}

# QQUANT GATES CERTIFICATION, RUN ON A SCHEDULE (principal decision 2026-08-23). Shadow entry no
# longer requires a certificate (shadow_forward.py/scalp_shadow.py admit every declared sleeve
# unconditionally now -- see that commit), but LIVE PROMOTION still does: promoter.py refuses
# anything without a real pass in QQUANT_GATES.json/REAL_SURVIVORS.json/UNIVERSAL_SURVIVORS.json.
# Verified live on this box 2026-08-23: neither QQUANT_GATES.json nor REAL_SURVIVORS.json existed
# at all -- the certificate step had never been run here, not merely gone stale. Running it once by
# hand answers today's question; running it daily is what stops today's question from recurring
# every time shadow accrues enough evidence for a sleeve to be worth re-checking. 23:00 UTC: after
# the 22:00 UTC gateway/shadow_forward/promoter cycle has written the day's shadow state, so the
# certification run sees the freshest evidence rather than racing it.
$qquantGates = Join-Path $DeskRoot "research\qquant_gates.py"
if (Test-Path $qquantGates) {
    if ($WhatIfOnly) {
        Write-Host "  [DRY ] MT5-QQuantGatesCertify daily original 10-gate certification run"
    } else {
        try {
            $qgLog = Join-Path $logDir "MT5-QQuantGatesCertify.log"
            $qgCmd = "/d /s /c `"`"$Python`" $pyArgs`"$qquantGates`" >> `"$qgLog`" 2>&1`""
            $qgAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $qgCmd `
                -WorkingDirectory $DeskRoot
            $qgTrigger = New-ScheduledTaskTrigger -Daily -At "23:00"
            $qgSettings = New-ScheduledTaskSettingsSet `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
                -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10) `
                -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
            $qgPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
                -LogonType Interactive -RunLevel Limited
            Unregister-ScheduledTask -TaskName "MT5-QQuantGatesCertify" `
                -Confirm:$false -ErrorAction SilentlyContinue
            Register-ScheduledTask -TaskName "MT5-QQuantGatesCertify" -Action $qgAction `
                -Trigger $qgTrigger -Settings $qgSettings -Principal $qgPrincipal `
                -Description "Daily original-10-gate certification (QQUANT_GATES.json) -- the only thing promoter.py accepts for live promotion." | Out-Null
            Write-Host "  [OK  ] MT5-QQuantGatesCertify registered"
        } catch {
            Write-Host ("  [FAIL] MT5-QQuantGatesCertify {0}" -f $_.Exception.Message)
        }
    }
} else {
    Write-Host "  [SKIP] MT5-QQuantGatesCertify research\qquant_gates.py not found"
}

# ---- THE LINK THAT WAS NOT AUTOMATIC ---------------------------------------
# quant EXPORTS findings daily (daily_cycle step 4) and Aurum READS them daily
# (aurum_cycle step_absorb). Both ends ran on a schedule; NOTHING CARRIED THE
# FILE BETWEEN THEM. A pipe whose middle section is a human remembering to run a
# script is a pipe that stops the first busy week, and it stops SILENTLY --
# Aurum keeps reporting "0 new findings", which reads exactly like the quant
# desk having learned nothing.
#
# Runs at 22:15 UTC, after the 21:45 daily cycle has written the export. The
# script is idempotent on (statement, measured_on), so an early or repeated run
# appends nothing rather than duplicating.
if ($AurumRoot) {
    $syncScript = Join-Path $AurumRoot "deploy\windows\Sync-QuantFindings.ps1"
    if (-not (Test-Path $syncScript)) {
        Write-Host ("  [SKIP] {0,-14} not found at {1}" -f "Aurum-Sync", $syncScript)
    } elseif ($WhatIfOnly) {
        Write-Host ("  [DRY ] {0,-14} {1}" -f "Aurum-Sync", $syncScript)
    } else {
        $quantRoot = Split-Path -Parent (Split-Path -Parent $DeskRoot)
        $sa = New-ScheduledTaskAction -Execute "powershell.exe" `
            -Argument ("-NoProfile -ExecutionPolicy Bypass -File `"$syncScript`" " +
                       "-QuantRoot `"$quantRoot`" -AurumRoot `"$AurumRoot`"") `
            -WorkingDirectory $AurumRoot
        $stg = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 `
            -RestartInterval (New-TimeSpan -Minutes 5) `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
        # NOT SYSTEM, and NOT RunLevel Highest. Both were tried and both threw
        # the identical "Access is denied" (0x80070005) from Register-Scheduled
        # Task -- SYSTEM needs SeAssignPrimaryTokenPrivilege/SeIncreaseQuotaPriv
        # ilege to impersonate via CIM, and several VPS base images (Contabo's
        # included) restrict elevated-run-level task CREATION even from an
        # account named Administrator, independent of which account owns it.
        # MT5-ShadowSync registers successfully on this same box with the same
        # interactive account at RunLevel Limited -- that is the only
        # combination proven to register here, and the sync script needs no
        # elevation: it only reads quant's export and writes into Aurum's own
        # inbox, both already owned by this user.
        $syncPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
            -LogonType Interactive -RunLevel Limited
        try {
            Unregister-ScheduledTask -TaskName "Aurum-Sync" -Confirm:$false -ErrorAction SilentlyContinue
            Register-ScheduledTask -TaskName "Aurum-Sync" -Action $sa `
                -Trigger (New-ScheduledTaskTrigger -Daily -At "22:15") -Settings $stg `
                -Description "Carry quant's exported findings into Aurum's absorption inbox." `
                -Principal $syncPrincipal -ErrorAction Stop | Out-Null
            Write-Host ("  [OK  ] {0,-14} daily 22:15 -> {1}" -f "Aurum-Sync", $AurumRoot)
        } catch {
            Write-Host ("  [FAIL] {0,-14} {1}" -f "Aurum-Sync", $_.Exception.Message)
        }
    }
} else {
    Write-Host ""
    Write-Host "  NOTE: -AurumRoot not given, so the findings transport is NOT scheduled."
    Write-Host "        quant will export daily and Aurum will read daily, but nothing"
    Write-Host "        moves the file between them. Re-run with -AurumRoot C:\Aurum."
}

Write-Host ""
Write-Host "VERIFY -- these are the only checks that mean anything:"
Write-Host "  Get-ScheduledTask MT5-Gateway,MT5-Hourly | Select TaskName,State"
Write-Host "  Start-ScheduledTask -TaskName MT5-Hourly     # force one run now"
Write-Host "  Get-Content logs\MT5-Hourly.log -Tail 40"
Write-Host "  Get-Content reports\shadow\shadow_state.json | Select-Object -First 30"
Write-Host ""
Write-Host "SHADOW IS THE THING TO WATCH. Every sleeve sits at n=0 until bars"
Write-Host "reach it. If they stay at 0 after a run, logs\shadow.log names the"
Write-Host "reason per symbol -- it is a data question, never a silent one."
Write-Host ""
Write-Host "All recurring tasks use the interpreter and checkout printed above;"
Write-Host "no research target carries a second machine-specific Python path."
