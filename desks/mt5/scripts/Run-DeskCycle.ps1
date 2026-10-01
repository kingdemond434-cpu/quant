<#
.SYNOPSIS
    Run one lane of the daily desk cycle: NOON (Claude, 12:00) or MIDNIGHT (Codex, 00:00).

.DESCRIPTION
    Two autonomous passes run twelve hours apart against this repository and the live box. BOTH
    RUN THE SAME PROCEDURE, `docs/cro/CRO_CYCLE.md`, under `docs/cro/QUANT_CONSTITUTION.md`, with
    `docs/cro/QUANT_REFERENCE.md` consulted on demand; the lane selects a time slot and a
    checkpoint file, nothing else. `docs/DESK_CYCLE_PROMPT.md` stays as the box-mechanics annex.

    THE CLOCK IS EUROPE/DUBLIN, NOT THE BOX'S. The principal asked for 12:00 Irish time, and a
    Windows trigger fires on the box's local clock, which is a different zone and changes DST on
    its own rules. So the scheduler fires the launcher every hour and the launcher decides, on
    the Dublin clock, whether its lane's window is open: NOON 12:00-22:59, MIDNIGHT 00:00-10:59.
    A firing outside the window costs one clock read and exits 0.

    ONE CONTROLLER AT A TIME. The pass claims the canonical controller lease
    (`libs/ops/controller_continuity.py`, via `scripts/controller_checkpoint.py`) before the agent
    starts and releases it after. A lane that overruns into the other's window holds the lease, so
    the other lane is refused and retries on the next hourly firing rather than editing the same
    repository at the same time.

    A split scope would mean half the work stops the day one agent's CLI is missing or its
    credential expires -- and the half that stopped is invisible, because the other half keeps
    reporting success. Two complete passes by two different agents means every check runs twice a
    day, and what one misses the other can still find. They never overlap (ten-hour bound,
    repetition stops at eleven), so they cannot collide.

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
    `noon` or `midnight`. Same work; different slot and checkpoint.

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
$Prompt   = Join-Path $RepoRoot "docs\cro\CRO_CYCLE.md"
$Constitution = Join-Path $RepoRoot "docs\cro\QUANT_CONSTITUTION.md"
$Reference    = Join-Path $RepoRoot "docs\cro\QUANT_REFERENCE.md"
$Ledger   = Join-Path $DeskRoot "data\cro_cycle_ledger.jsonl"
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
$OtherLane = if ($Lane -eq "noon") { "midnight" } else { "noon" }
$OtherStateFile = Join-Path $DeskRoot ("data\cycle_state_{0}.json" -f $OtherLane)

# "GMT Standard Time" is the Windows id for Europe/Dublin (and London): GMT in winter, IST in
# summer. The lane's date and window are both read on that clock.
$DublinZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("GMT Standard Time")
$DublinNow  = [System.TimeZoneInfo]::ConvertTimeFromUtc((Get-Date).ToUniversalTime(), $DublinZone)
$Today = $DublinNow.ToString("yyyy-MM-dd")
$WindowStart = if ($Lane -eq "noon") { 12 } else { 0 }
$WindowEnd   = $WindowStart + 11            # exclusive; one clear hour before the other lane
if ($DublinNow.Hour -lt $WindowStart -or $DublinNow.Hour -ge $WindowEnd) {
    if (-not $WhatIfOnly) {
        # Not logged: twenty-four firings a day would bury the lines that matter.
        exit 0
    }
    Write-Host ("[{0}] outside window: Dublin {1:HH:mm}, lane runs {2:00}:00-{3:00}:59 -- dry run continues" -f
                $Lane, $DublinNow, $WindowStart, ($WindowEnd - 1))
}

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

# ONCE A DAY, AT THE SLOT (principal, 2026-09-29: "run once only at 12 pm noon"). A FRESH pass
# starts only in the lane's first hour -- 12:xx Dublin for Claude, 00:xx for Codex. The later
# hourly firings exist solely to RESUME a pass that today's slot started and something cut off;
# with no unfinished pass for today they exit 0 on one file read and write nothing.
$pre = Get-CycleState
$unfinishedToday = $pre -and $pre.date -eq $Today -and $pre.status -eq "RUNNING"
if (-not $WhatIfOnly -and -not $unfinishedToday -and $DublinNow.Hour -ne $WindowStart) {
    exit 0
}

Write-Cycle ("cycle start (Dublin {0:yyyy-MM-dd HH:mm})" -f $DublinNow)
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

if (-not (Test-Path -LiteralPath $Prompt) -or -not (Test-Path -LiteralPath $Constitution)) {
    # The prompt IS the pass. Running an agent against this repository with no instructions is
    # strictly worse than not running one, so this is fatal rather than a warning.
    Write-Cycle "FATAL: CRO_CYCLE.md or QUANT_CONSTITUTION.md missing under docs\cro -- refusing to run an agent with no brief"
    exit 2
}

if (-not $AgentCommand) {
    $AgentCommand = if ($Lane -eq "noon") { "claude" } else { "codex" }
}

# A scheduled task's PATH is the machine PATH, not the shell PATH of whoever installed the CLI,
# so the per-user install locations are tried explicitly before giving up.
$resolved = Get-Command $AgentCommand -ErrorAction SilentlyContinue
if (-not $resolved) {
    $candidates = @(
        (Join-Path $env:USERPROFILE ".local\bin\$AgentCommand.exe"),
        (Join-Path $env:APPDATA "npm\$AgentCommand.cmd"),
        "C:\Users\Administrator\.local\bin\$AgentCommand.exe",
        "C:\Users\Administrator\AppData\Roaming\npm\$AgentCommand.cmd"
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { $resolved = Get-Command $c; break }
    }
}
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

# HEADLESS, WITH SCOPED PERMISSIONS. Piping a brief into a bare `claude` or `codex` opens the
# interactive UI, which has no console under Task Scheduler and dies before reading a word -- the
# lane would "run" every day and do nothing. Each CLI gets its non-interactive entry point, and
# neither gets a blanket permission bypass: file edits and the named command families only, with
# history rewrites and the deadman rail refused by the CLI itself, not just by the brief.
$agentName = [System.IO.Path]::GetFileNameWithoutExtension($resolved.Source).ToLowerInvariant()
$agentArgs = @()

# READ-ONLY WIDENING, FROM ONE LIST. In -p mode a tool outside --allowedTools is refused without a
# prompt and the pass carries on, so a step that needed WebFetch or a plain `ls` silently never
# ran. The WebFetch hosts come from ops\agent_webfetch_domains.json -- the one list, whose every
# host is `confirmed` on the alt_proxies TERMS gate -- never from a copy here. A malformed host is
# dropped and logged rather than handed to the CLI as a rule.
$DomainsFile = Join-Path $RepoRoot "ops\agent_webfetch_domains.json"
$webFetchRules = @()
try {
    foreach ($row in @((Get-Content -LiteralPath $DomainsFile -Raw | ConvertFrom-Json).domains)) {
        $host_ = "$($row.domain)".Trim()
        if ($host_ -cmatch '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$') {
            $webFetchRules += ("WebFetch(domain:{0})" -f $host_)
        } else {
            Write-Cycle "WARN: skipped malformed WebFetch host '$host_' in $DomainsFile"
        }
    }
} catch {
    Write-Cycle ("WARN: WebFetch domain list unreadable ({0}) -- WebFetch stays refused, and every refusal is recorded as MISSED" -f $_.Exception.Message)
}

if ($agentName -eq "claude") {
    # stream-json, not text: it is the only output that says which tool calls were REFUSED
    # (system/permission_denied events and the result's permission_denials). The stream is teed
    # to disk and scripts\record_agent_denials.py turns each refusal into an UNMEASURED = MISSED
    # ledger row after the pass. --verbose is required by the CLI for stream-json under -p.
    $agentArgs = @(
        "-p", "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits",
        "--allowedTools",
        "Read", "Edit", "Write", "Glob", "Grep",
        "Bash(git status:*)", "Bash(git log:*)", "Bash(git diff:*)", "Bash(git show:*)",
        "Bash(git fetch:*)", "Bash(git worktree:*)", "Bash(git add:*)", "Bash(git commit:*)",
        "Bash(git rebase:*)", "Bash(git push origin:*)", "Bash(git rev-parse:*)",
        "Bash(python:*)", "Bash(py:*)", "Bash(pytest:*)",
        # Read-only shell the steps use to look around; nothing here writes, pushes or reads secrets.
        "Bash(ls:*)", "Bash(pwd)", "Bash(date)", "Bash(date -u:*)", "Bash(wc:*)"
    ) + $webFetchRules + @(
        "--disallowedTools",
        "Bash(git push --force:*)", "Bash(git push -f:*)", "Bash(git reset --hard:*)",
        "Bash(git stash:*)", "Bash(git commit -a:*)", "Edit(scripts/run_deadman_switch.py)",
        "Write(scripts/run_deadman_switch.py)", "Read(data/secrets/**)"
    )
} elseif ($agentName -eq "codex") {
    # --full-auto is Codex's sandboxed unattended mode (workspace-write, no approval prompts).
    $agentArgs = @("exec", "--full-auto", "-")
}
$streamJson = ($agentName -eq "claude")
$Stream = Join-Path $LogDir ("cycle_{0}_stream.jsonl" -f $Lane)
$Review = Join-Path $DeskRoot "reports\TIER1_BREADTH_REVIEW.json"

$resumeNote = if ($resuming) {
@"

THIS IS A RESUMED PASS. A previous run today was cut off -- by the execution time limit or by the
box going down -- and these stages are ALREADY COMPLETE. Do not redo them:

$($done | ForEach-Object { "  - $_" } | Out-String)
Continue from where that pass stopped. Re-running a finished stage costs the hours the late
stages need, which is how a pass ends up always beginning and never finishing.
"@
} else { "" }

$ReleaseFile = Join-Path $DeskRoot "data\RELEASE.json"
function Get-Identity {
    $head = (& git -C $RepoRoot rev-parse HEAD 2>$null | Out-String).Trim()
    $branch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
    $rel = $null
    if (Test-Path -LiteralPath $ReleaseFile) {
        try { $rel = Get-Content -LiteralPath $ReleaseFile -Raw | ConvertFrom-Json } catch { $rel = $null }
    }
    return @{ head = $head; branch = $branch; release = $rel }
}

function Add-LedgerRow([hashtable] $Row) {
    $dir = Split-Path $Ledger -Parent
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Add-Content -LiteralPath $Ledger -Value ($Row | ConvertTo-Json -Depth 8 -Compress) -Encoding UTF8
}

# ---- THE LEASE: ONE CONTROLLER MUTATES THE INSTITUTION AT A TIME -----------------------------
$Controller = "{0}-{1}" -f $agentName, $Lane
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python -ErrorAction SilentlyContinue).Source }
$LeaseEpoch = 0
if (-not $WhatIfOnly) {
    # Eleven hours: longer than the ten-hour time limit, so a live pass never loses its own lease,
    # and short enough that a killed pass frees the institution before the other lane's window.
    $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    Push-Location $RepoRoot
    $claimJson = (& $Python scripts\controller_checkpoint.py claim --controller $Controller --ttl-seconds 39600 2>&1 | Out-String)
    Pop-Location
    $ErrorActionPreference = $prevEap
    try { $lease = $claimJson | ConvertFrom-Json } catch { $lease = $null }
    if (-not $lease -or $lease.status -ne "LEASED") {
        $why = if ($lease) { "{0} held by {1} until {2}" -f $lease.status, $lease.controller, $lease.expires_at } else { $claimJson.Trim() }
        Write-Cycle "lease NOT acquired ($why) -- refusing a second controller; the next hourly firing retries"
        # Non-zero so a lane that never gets the lease is visible in the task history.
        exit 5
    }
    $LeaseEpoch = [int]$lease.epoch
    $env:QUANT_CONTROLLER = $Controller
    $env:QUANT_CONTROLLER_EPOCH = "$LeaseEpoch"
    $env:QUANT_CONTROLLER_TOKEN = $lease.fencing_token      # never logged
}

$brief = @"
You are the $($Lane.ToUpper()) lane of the CRO cycle, run headless by the box scheduler
($agentName). Both lanes execute the SAME procedure on ONE canonical institution.

LOAD ORDER (do not spend the pass re-summarizing these):
  1. docs/cro/CRO_CYCLE.md          -- READ FIRST. This is the procedure you execute.
  2. docs/cro/QUANT_CONSTITUTION.md -- governing law for every step.
  3. docs/cro/QUANT_REFERENCE.md    -- ON DEMAND ONLY: open just the section for the subsystem
                                       that is failing, binding, due a deep audit or being changed.
  Higher sealed policy still wins: ops/principal_doctrine.txt and docs/LAWS.md.
  Box mechanics (tasks, gateway, release, paths) are in docs/DESK_CYCLE_PROMPT.md -- consult it
  on demand, as you would the reference.

Repository root: $RepoRoot
Dublin time now: $($DublinNow.ToString("yyyy-MM-dd HH:mm"))
Controller lease: '$Controller' epoch $LeaseEpoch, claimed by the launcher (QUANT_CONTROLLER_*
  are set in your environment). After each material closure run
  python scripts/controller_checkpoint.py checkpoint --note "<item id: disposition>"
$resumeNote
STEP 2 INPUT -- THE OTHER LANE'S LAST PASS. Verify its material work independently; never trust
its report. Its checkpoint (work_items[] carries commits, tests and release identity):

    $OtherStateFile

The shared history of every pass is $Ledger (one JSON row per start and end).

ISOLATION. Other sessions may be editing the live checkout at $RepoRoot. Never edit code there
directly and never git stash / commit -a. Make code changes in a worktree
(git worktree add ..\quant-cro-$Lane -B cro/$Lane-$Today origin/<box branch>), test there, rebase
on origin/<box branch> and push to that branch. MT5-AdoptRelease adopts origin into the live tree
hourly and records the release in desks/mt5/data/RELEASE.json: that is the canonical release path.
Remove the worktree when done.

AUTHORITY. Do not change validated live trading logic, live certificate/registry state, arming or
allocation unless an existing authorization record covers it; otherwise disposition the item as
BLOCKED_BY_EXACT_EXTERNAL_CONSTRAINT naming the exact approval needed. Never touch
scripts/run_deadman_switch.py. Never stop or pause research workers.

CHECKPOINT, AND IT IS PART OF THE WORK. This file is your resume point and the next lane's input:

    $StateFile

Keep `status` as "RUNNING". After each CRO_CYCLE step append its name (e.g. "STEP 3 CENSUS") to
`completed`. For each material item append to `work_items` an object with: id, title, binding
constraint, disposition (one of the five in CRO_CYCLE step 8), commit, tests, independent_check,
release_sha (RELEASE.json after adoption, or "PENDING_ADOPTION"), consumption_proof,
remaining_gap, reopen_trigger, next_action. Also set `binding_constraint` and `report` (the
eleven-line COMPACT REPORT). The launcher marks DONE only on a clean exit.

THIS IS AN ACTION CYCLE, NOT A REPORTING CYCLE.
STEP 4B (the daily tier-1 breadth review) runs every pass: answer from live data whether breadth, production and global ingestion are maxed out at tier-1 level and what tier the quant is today, rank the gaps, act on the biggest, and write desks/mt5/reports/TIER1_BREADTH_REVIEW.json.
Duties D15-D26 (judging rate, UNKNOWN by cause, box state freshness, unfed datasets, paid substitutes, cross-culture orthogonality, live code drift, decay and markout, confident kills, credentials, pass-2 queue age, six-event trend) are checked every pass with their artifacts; an absent artifact is UNMEASURED, which is MISSED.
REFUSED TOOLS ARE RECORDED. A tool call outside this lane's allowlist is refused, and the launcher records each refusal in the CRO ledger as UNMEASURED (counts_as MISSED) and marks the duty that step served MISSED in TIER1_BREADTH_REVIEW.json. Never score a duty MET when a step it needed was refused; name the refused step and its disposition instead. WebFetch is granted only for the hosts in ops/agent_webfetch_domains.json.
"@

if ($WhatIfOnly) {
    Write-Cycle ("DRY RUN -- would run: {0} {1} (brief on stdin, {2} chars)" -f
                 $resolved.Source, ($agentArgs -join " "), $brief.Length)
    Write-Host $brief
    exit 0
}

Set-CycleState @{
    lane = $Lane; date = $Today; status = "RUNNING"
    pid = $PID; started_at = (Get-Date -Format "o")
    completed = $done
    work_items = $(if ($resuming -and $state.work_items) { @($state.work_items) } else { @() })
    resumed = $(if ($resuming) { [int]$state.resumed + 1 } else { 0 })
    controller = $Controller; lease_epoch = $LeaseEpoch
    why = "written by Run-DeskCycle.ps1; the agent appends to completed[] and work_items[]"
}

$startIdentity = Get-Identity
Add-LedgerRow @{
    event = "start"; lane = $Lane; agent = $agentName; date = $Today
    at = (Get-Date).ToUniversalTime().ToString("o"); pid = $PID
    controller = $Controller; lease_epoch = $LeaseEpoch; resumed = $resuming
    head = $startIdentity.head; branch = $startIdentity.branch
    release_code_sha = $(if ($startIdentity.release) { $startIdentity.release.code_sha } else { $null })
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
    Push-Location $RepoRoot
    try {
        # The claude lane speaks stream-json: every line goes to $Stream (utf-8, one event per
        # line) and only non-JSON lines (the CLI's stderr) reach the human log directly; the
        # pass's final result text is written into the log by record_agent_denials.py below.
        if ($streamJson) { Set-Content -LiteralPath $Stream -Value $null -Encoding UTF8 }
        $brief | & $resolved.Source @agentArgs 2>&1 | ForEach-Object {
            $text = "$_"
            if ($streamJson) {
                Add-Content -LiteralPath $Stream -Value $text -Encoding UTF8
                if (-not $text.StartsWith("{")) {
                    Write-Host $text
                    Add-Content -LiteralPath $Log -Value $text
                }
            } else {
                Write-Host $text
                Add-Content -LiteralPath $Log -Value $text
            }
        }
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
        $ErrorActionPreference = $prev
    }
} catch {
    Write-Cycle ("FATAL: agent invocation raised: {0}" -f $_.Exception.Message)
    exit 4
}

# EVERY REFUSED STEP IS A MISSED STEP, AND IT LEAVES A ROW. The recorder reads the teed stream,
# writes the pass's result text into the human log, appends one UNMEASURED / counts_as MISSED row
# per refused tool call to the CRO ledger, and marks the duty each refused step served MISSED in
# the TIER1_BREADTH_REVIEW.json this pass wrote. Its failure is logged, never the task's exit code.
$deniedCount = $null
if ($streamJson) {
    $prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    Push-Location $RepoRoot
    $recJson = (& $Python scripts\record_agent_denials.py --stream $Stream --ledger $Ledger `
                    --log $Log --review $Review --started-at $started.ToUniversalTime().ToString("o") `
                    --surface cro_cycle --lane $Lane --agent $agentName --date $Today 2>&1 | Out-String)
    Pop-Location
    $ErrorActionPreference = $prevEap
    try { $rec = ($recJson.Trim() -split "`n")[-1] | ConvertFrom-Json } catch { $rec = $null }
    if ($rec -and $rec.status -eq "RECORDED") {
        $deniedCount = [int]$rec.denials
        Write-Cycle ("permission denials: {0} (each recorded UNMEASURED, counts as MISSED); duties marked MISSED: {1}" -f
                     $deniedCount, (@($rec.changed_duties) -join ","))
    } else {
        Write-Cycle ("permission denials UNMEASURED: recorder failed ({0})" -f $recJson.Trim())
    }
}

$mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)

# STEP 9, MEASURED BY THE LAUNCHER TOO: research must still be dispatching after the pass. The
# agent's word for it is not evidence; the supervisor task's state is.
$sup = Get-ScheduledTask -TaskName "MT5-ResearchSupervisor" -ErrorAction SilentlyContinue
$supState = if ($sup) { "$($sup.State)" } else { "ABSENT" }
Write-Cycle "research supervisor after pass: $supState"

# DONE ONLY ON A CLEAN EXIT. Any other ending -- non-zero, killed by the time limit, box down --
# leaves the checkpoint RUNNING, which is exactly what makes the next hourly firing resume rather
# than start over. Marking DONE on a bad exit would silently convert an interrupted pass into a
# finished one, and the stages it never reached would wait a full day.
$final = Get-CycleState
$completed = if ($final) { @($final.completed) } else { $done }
$items = if ($final -and $final.work_items) { @($final.work_items) } else { @() }
$binding = if ($final) { $final.binding_constraint } else { $null }
$report = if ($final) { $final.report } else { $null }
if ($code -eq 0) {
    Set-CycleState @{
        lane = $Lane; date = $Today; status = "DONE"; pid = $PID
        started_at = $started.ToString("o"); finished_at = (Get-Date -Format "o")
        completed = $completed; minutes = $mins; work_items = $items
        binding_constraint = $binding; report = $report
        controller = $Controller; lease_epoch = $LeaseEpoch
        research_supervisor = $supState
        resumed = $(if ($final) { $final.resumed } else { 0 })
    }
    Write-Cycle ("marked DONE for {0} ({1} stage(s) recorded)" -f $Today, $completed.Count)
} else {
    Set-CycleState @{
        lane = $Lane; date = $Today; status = "RUNNING"; pid = 0
        started_at = $started.ToString("o"); last_exit = $code
        completed = $completed; work_items = $items
        binding_constraint = $binding; report = $report
        controller = $Controller; lease_epoch = $LeaseEpoch
        resumed = $(if ($final) { $final.resumed } else { 0 })
        why = "left RUNNING on a non-clean exit so the next hourly firing resumes it"
    }
    Write-Cycle ("left RESUMABLE: rc={0}, {1} stage(s) complete" -f $code, $completed.Count)
}

$endIdentity = Get-Identity
Add-LedgerRow @{
    event = "end"; lane = $Lane; agent = $agentName; date = $Today
    at = (Get-Date).ToUniversalTime().ToString("o"); rc = $code; minutes = $mins
    controller = $Controller; lease_epoch = $LeaseEpoch
    head = $endIdentity.head; branch = $endIdentity.branch
    release_code_sha = $(if ($endIdentity.release) { $endIdentity.release.code_sha } else { $null })
    completed = $completed; work_items = $items; binding_constraint = $binding
    research_supervisor = $supState
    permission_denials = $deniedCount
}

# Release the lease whatever the outcome, so the other lane is never locked out by a finished
# pass. A failed release is logged; the lease still expires on its own at the eleven-hour TTL.
$prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
Push-Location $RepoRoot
$rel = (& $Python scripts\controller_checkpoint.py checkpoint --note ("{0} pass end rc={1}" -f $Lane, $code) 2>&1 | Out-String)
$rel = (& $Python scripts\controller_checkpoint.py release 2>&1 | Out-String)
Pop-Location
$ErrorActionPreference = $prevEap
Write-Cycle ("lease released: {0}" -f ($(if ($rel -match '"RELEASED"') { "yes" } else { "NO -- expires at TTL" })))

Write-Cycle ("cycle end rc={0} after {1} min" -f $code, $mins)
# The agent's exit code is this task's exit code. A pass that ended badly must be visible in the
# task history, which is the only place anyone looks when the desk goes quiet.
exit $(if ($null -eq $code) { 0 } else { $code })
