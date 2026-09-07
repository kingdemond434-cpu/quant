<#
.SYNOPSIS
    Run one lane of the daily desk cycle: NOON (Claude, conversion) or MIDNIGHT (Codex, wiring).

.DESCRIPTION
    Two autonomous passes run twelve hours apart against this repository and the live box. Both
    execute `docs/DESK_CYCLE_PROMPT.md`; the lane decides which half of it they own. The lane
    split is not decoration -- it is what stops two agents editing the same files twelve hours
    apart and calling the result progress.

    WHAT THIS SCRIPT IS. A launcher and a log, nothing more. It resolves an agent CLI, hands it
    the prompt with the lane named, and records what happened. It contains no desk logic and no
    repair of its own: everything the pass does is in the prompt, where it can be read and
    argued with, rather than split between a document and a wrapper.

    IT FAILS LOUDLY WHEN THERE IS NO AGENT, and that is the whole design decision here. The
    obvious shape -- try the CLI, exit 0 if it is missing -- reproduces this desk's most expensive
    recurring defect exactly: `MT5-ShadowSync` fired every fifteen minutes and returned exit 0
    while publishing nothing for thirty-three hours, because its skip branch exited 0 when the
    sources were absent. Publishing nothing and publishing successfully were byte-identical to
    every watchdog. A scheduled task that cannot do its job must say so in its exit code, or the
    task list shows green forever.

    NO CREDENTIALS PASS THROUGH HERE. The agent CLI authenticates itself; this script neither
    reads nor forwards a key, and it never prints one.

.PARAMETER Lane
    `noon` (Claude, conversion and throughput) or `midnight` (Codex, wiring and repair).

.PARAMETER AgentCommand
    Override the CLI. Defaults to `claude` for noon and `codex` for midnight, which is the pairing
    the schedule installs. Any command that accepts a prompt on stdin works.

.PARAMETER WhatIfOnly
    Resolve everything and print the invocation without running the agent.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File desks\mt5\scripts\Run-DeskCycle.ps1 -Lane noon
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("noon", "midnight")]
    [string] $Lane,
    [string] $AgentCommand,
    [switch] $WhatIfOnly
)

$ErrorActionPreference = "Stop"

$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot "..\..")).Path
$Prompt   = Join-Path $RepoRoot "docs\DESK_CYCLE_PROMPT.md"
$LogDir   = Join-Path $DeskRoot "logs"
$Log      = Join-Path $LogDir ("cycle_{0}.log" -f $Lane)
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Cycle([string] $Message) {
    $line = "{0} [{1}] {2}" -f (Get-Date -Format "o"), $Lane, $Message
    Write-Host $line
    Add-Content -LiteralPath $Log -Value $line
}

# ---- THE CHECKPOINT: A CUT-OFF PASS RESUMES, IT DOES NOT RESTART -----------------------------
# These passes are long, and two things reliably interrupt them: the box being off at the trigger
# time, and the execution time limit landing mid-sweep. Restarting from stage one on the next
# firing would mean the expensive early stages run every time and the late ones never run at all
# -- a pass that always begins and never finishes, which is worse than a shorter pass that ends.
#
# So the lane keeps a checkpoint. The trigger fires HOURLY on top of its daily start: a firing
# that finds today's lane already DONE costs one file read and exits, a firing that finds it
# RUNNING with a dead process resumes it with the completed stages named, and a firing that finds
# nothing starts fresh. That is what makes it continue "right after it is back" rather than at
# the next daily slot -- the recovery window is an hour, not a day.
$StateFile = Join-Path $DeskRoot ("data\cycle_state_{0}.json" -f $Lane)
$Today = (Get-Date).ToString("yyyy-MM-dd")

function Get-CycleState {
    if (-not (Test-Path -LiteralPath $StateFile)) { return $null }
    try { return Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json }
    catch { return $null }        # an unreadable checkpoint means start fresh, never crash
}

function Set-CycleState([hashtable] $State) {
    $dir = Split-Path $StateFile -Parent
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    ($State | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $StateFile -Encoding UTF8
}

function Test-ProcessAlive([int] $ProcessId) {
    if (-not $ProcessId) { return $false }
    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

Write-Cycle "cycle start"
Write-Cycle "repo $RepoRoot"

$state = Get-CycleState
$resuming = $false
$done = @()

if ($state -and $state.date -eq $Today) {
    if ($state.status -eq "DONE") {
        Write-Cycle "already DONE for $Today (finished $($state.finished_at)) -- nothing to do"
        exit 0
    }
    if ($state.status -eq "RUNNING" -and (Test-ProcessAlive $state.pid)) {
        # Belt and braces beside MultipleInstances=IgnoreNew: two agents in one repository is the
        # collision the lane split exists to prevent, so it is refused here too.
        Write-Cycle "a pass is ALREADY RUNNING (pid $($state.pid)) -- not starting a second"
        exit 0
    }
    if ($state.status -eq "RUNNING") {
        $resuming = $true
        $done = @($state.completed)
        Write-Cycle ("RESUMING an interrupted pass: {0} stage(s) already complete, " -f $done.Count +
                     "previous pid $($state.pid) is gone")
    }
}

Set-CycleState @{
    lane = $Lane; date = $Today; status = "RUNNING"
    pid = $PID; started_at = (Get-Date -Format "o")
    completed = $done
    resumed = $(if ($resuming) { [int]$state.resumed + 1 } else { 0 })
    why = "written by Run-DeskCycle.ps1; the agent appends to completed[] as it finishes stages"
}

if (-not (Test-Path -LiteralPath $Prompt)) {
    # The prompt IS the pass. Running an agent against this repository with no instructions is
    # strictly worse than not running one, so this is fatal rather than a warning.
    Write-Cycle "FATAL: prompt not found at $Prompt -- refusing to run an agent with no brief"
    exit 2
}

if (-not $AgentCommand) {
    $AgentCommand = if ($Lane -eq "noon") { "claude" } else { "codex" }
}

$resolved = Get-Command $AgentCommand -ErrorAction SilentlyContinue
if (-not $resolved) {
    Write-Cycle "FATAL: agent command '$AgentCommand' is not on PATH for this task's account."
    Write-Cycle "  A scheduled task runs as a specific user; a CLI installed for a different"
    Write-Cycle "  profile, or into a shell-only PATH, is invisible here even though it works"
    Write-Cycle "  when you type it. Fix with one of:"
    Write-Cycle "    - install the CLI for the account this task runs as, or"
    Write-Cycle "    - pass -AgentCommand with the full path to the executable."
    Write-Cycle "  Exiting NON-ZERO on purpose: a task that cannot do its job must not report"
    Write-Cycle "  success, or the task list stays green while nothing runs."
    exit 3
}
Write-Cycle "agent $($resolved.Source)"

$resumeNote = if ($resuming) {
@"

THIS IS A RESUMED PASS. A previous run today was cut off -- by the execution time limit or by the
box going down -- and these stages are ALREADY COMPLETE. Do not redo them:

$($done | ForEach-Object { "  - $_" } | Out-String)
Continue from where that pass stopped. Re-running a finished stage costs the hours the late
stages need, which is how a pass ends up always beginning and never finishing.
"@
} else { "" }

$brief = @"
You are the $($Lane.ToUpper()) lane of the desk cycle.

Read docs/DESK_CYCLE_PROMPT.md in full and execute YOUR LANE ONLY -- section VI for noon,
section VII for midnight. Sections I through V and VIII through IX bind both lanes.

Repository root: $RepoRoot
$resumeNote
CHECKPOINT, AND IT IS PART OF THE WORK. This file is your resume point:

    $StateFile

After finishing each numbered stage of your lane, append that stage's name to `completed` and
rewrite the file, keeping `status` as "RUNNING". A pass that does all the work and checkpoints
none of it is a pass that starts from stage one tomorrow. Leave `status` alone at the end -- the
launcher marks DONE only when the agent exits cleanly, so a crash correctly reads as unfinished.

The laws in section I are absolute. Report what you MEASURED, not what you changed. Every repair
ships with a fixer. Refusals are output, not silence: a pass that reports only what it did, and
not what it declined, is reporting half its work.
"@

if ($WhatIfOnly) {
    Write-Cycle "DRY RUN -- would run: $($resolved.Source) (prompt on stdin, $($brief.Length) chars)"
    exit 0
}

$started = Get-Date
try {
    # Stdin rather than an argument: the brief is multi-line and quoting it through Task
    # Scheduler -> cmd -> PowerShell -> the CLI is four chances to mangle it.
    #
    # `Stop` is relaxed around the native call for the reason documented in Adopt-Release.ps1 and
    # sync_shadow_to_git.ps1: PowerShell turns each stderr LINE from an external program into an
    # ErrorRecord, and under Stop the first one terminates the script -- so ordinary agent
    # progress written to stderr would kill the pass. Exit code is the truth.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $brief | & $resolved.Source 2>&1 | ForEach-Object {
            $text = "$_"
            Write-Host $text
            Add-Content -LiteralPath $Log -Value $text
        }
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
} catch {
    Write-Cycle ("FATAL: agent invocation raised: {0}" -f $_.Exception.Message)
    exit 4
}

$mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)

# DONE ONLY ON A CLEAN EXIT. Any other ending -- non-zero, killed by the time limit, box down --
# leaves the checkpoint RUNNING, which is exactly what makes the next hourly firing resume rather
# than start over. Marking DONE on a bad exit would silently convert an interrupted pass into a
# finished one, and the stages it never reached would wait a full day.
$final = Get-CycleState
$completed = if ($final) { @($final.completed) } else { $done }
if ($code -eq 0) {
    Set-CycleState @{
        lane = $Lane; date = $Today; status = "DONE"; pid = $PID
        started_at = $started.ToString("o"); finished_at = (Get-Date -Format "o")
        completed = $completed; minutes = $mins
        resumed = $(if ($final) { $final.resumed } else { 0 })
    }
    Write-Cycle ("marked DONE for {0} ({1} stage(s) recorded)" -f $Today, $completed.Count)
} else {
    Set-CycleState @{
        lane = $Lane; date = $Today; status = "RUNNING"; pid = 0
        started_at = $started.ToString("o"); last_exit = $code
        completed = $completed
        resumed = $(if ($final) { $final.resumed } else { 0 })
        why = "left RUNNING on a non-clean exit so the next hourly firing resumes it"
    }
    Write-Cycle ("left RESUMABLE: rc={0}, {1} stage(s) complete" -f $code, $completed.Count)
}
Write-Cycle ("cycle end rc={0} after {1} min" -f $code, $mins)
# The agent's exit code is this task's exit code. A pass that ended badly must be visible in the
# task history, which is the only place anyone looks when the desk goes quiet.
exit $(if ($null -eq $code) { 0 } else { $code })
