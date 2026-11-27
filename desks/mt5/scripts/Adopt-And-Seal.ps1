<#
.SYNOPSIS
    Adopt the branch's code onto this box, re-seal the release, restart the gateway.
    Hourly, unattended. The desk was never meant to wait for a person at a keyboard.

.DESCRIPTION
    THE FAILURE THIS EXISTS FOR (2026-09-08)

    Every fix for the desk lands on the branch the box pulls from. The box pushed its own
    state to that branch hourly and never pulled anything back, so for a full day the gateway
    ran on a tree that could not import `libs`, sized off base rather than the allocator's
    book, and refused every new order with

        RELEASE IDENTITY refuses NEW risk: running 92480baa4c66 vs sealed ca12b75a8a7f;
        money path drifted on disk

    while the fix for each of those sat on origin. Two live gold sleeves and three promotion
    candidates placed nothing. The only thing between the fix and the box was a human typing
    `git merge`, and that human was being handed the commands over chat.

    WHAT THIS DOES, IN THE ORDER THAT IS THE SAFETY PROPERTY

        Adopt-Release.ps1     lands the branch's tree by rewriting file CONTENTS in place
                              (survives a locked or NTFS-damaged path that makes git's unlink
                              fail), commits the box's own uncommitted state as itself, and
                              records the merge only after verifying tree == ref.
        seal, IF NEEDED       only when HEAD is not already the sealed code_sha, and only on a
                              tree with no tracked modification -- `release.seal` refuses a dirty
                              tree and so does this script, loudly, before calling it.
        commit RELEASE.json   ALONE. That pure-seal commit is what `release.accepts` recognises;
                              anything else in the same commit would be code the seal never named.
        restart MT5-Gateway   the gateway reads the seal at start. Restarting it is what turns a
                              new seal into new risk being placed.

    A partial adoption (non-zero from Adopt-Release) is NOT sealed: sealing a tree that only
    half-matches the branch would sign code nobody reviewed. The exit code carries through so the
    task history shows it.

    WHAT IT NEVER DOES

    No `git add -A`, no `git stash`, no force of any kind. It stages exactly one path by name.
    Anything it refuses to do it says in the log, with the reason, and exits non-zero.

.PARAMETER RepoRoot
    Repository root. Defaults to three levels above this script.

.PARAMETER Branch
    Branch to adopt. Defaults to the live desk branch named in CLAUDE.md.

.PARAMETER GuardRoot
    MANUAL RUNS ONLY (ops\box\adopt_once.cmd); the scheduled task never passes it. A clean
    checkout of a release commit whose adopt guard and release gate scripts
    decide this run instead of the running tree's copies, against -RepoRoot. Nothing is skipped:
    every check runs, in the same order, from audited release code. It exists because a guard
    that cannot read a record its successor fixed (11-14: the old parse_clears refusing a
    multi-line ADOPT_CLEARS row, which #1216 reads) refuses every release, and the fix can only
    arrive through the adoption it blocks. Refused unless its HEAD is an ancestor of the target.
#>
param(
    [string] $RepoRoot,
    [string] $Branch = "claude/llm-auto-upgrade-verify-gcjac3",
    # Adopt the branch tip even when no green release covers it -- the escape hatch for the day
    # CI is down and a fix must land. The file desks\mt5\data\ADOPT_UNRELEASED and the variable
    # QUANT_ADOPT_UNRELEASED=1 do the same for the scheduled task. Each is logged by name.
    [switch] $AllowUnreleased,
    # See .PARAMETER GuardRoot. Logged by name on every run that uses it.
    [string] $GuardRoot,
    # (boot r24.1, Audit C4) THE PINNED ADOPTER: the scheduled task runs this script from the
    # owner-installed checkout C:\ProgramData\QuantBox\guard\adopt\tree with -GuardRoot set to
    # it. As SYSTEM it then executes nothing from -RepoRoot: python is the pinned one, the guard's
    # helpers are its own (QUANT_ADOPT_PINNED=1), git never runs the tree's hooks or fsmonitor,
    # and the tree's code is first imported by the restarted non-admin gateway.
    [switch] $Pinned
)

# NATIVE STDERR IS NOT AN ERROR. git reports a successful fetch on stderr; under `Stop` that
# terminated Adopt-Release on its first run (test_powershell_native_stderr_is_guarded). Exit
# codes are checked explicitly below instead.
$ErrorActionPreference = "Continue"

if (-not $RepoRoot) { $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path }
Set-Location $RepoRoot
$desk    = Join-Path $RepoRoot "desks\mt5"
$release = Join-Path $desk "data\RELEASE.json"
# THE INTERPRETER, RESOLVED THE WAY THE INSTALLER RESOLVES IT: the repo venv, then the Windows
# launcher `py -3` (every scheduled task on this box runs through it), then bare `python`. The
# first version fell straight from the venv (which this box does not have) to `python`, and a
# box where that name is not on the task's PATH would have exited 4 at the seal -- adopted, never
# sealed, gateway still refusing on the old seal, and the whole run reading as "it ran".
if ($Pinned) {
    # (Audit C4, r24.2) AS SYSTEM, NOTHING UNDER -RepoRoot IS EVER EXECUTED OR IMPORTED. The
    # interpreter is the guard's own venv (install_guard builds it outside C:\opt and refuses a
    # base that quantrun can write); PYTHONSAFEPATH keeps the working directory and every script's
    # folder off sys.path, so `-c "from libs.ops ..."` below imports the guard checkout's libs; and
    # this probe refuses to adopt at all if any sys.path entry still sits under -RepoRoot. The tree
    # is only ever DATA here: git reads it, the deciders measure it, release.seal(root=) writes it.
    if (-not $GuardRoot) { "adopt-and-seal: -Pinned needs -GuardRoot"; exit 2 }
    $pinPy = Join-Path (Split-Path -Parent $GuardRoot) "python.txt"
    if (-not (Test-Path -LiteralPath $pinPy)) { "adopt-and-seal: -Pinned has no $pinPy"; exit 2 }
    $py = (Get-Content -LiteralPath $pinPy -TotalCount 1).Trim(); $pyArgs = @()
    $env:QUANT_ADOPT_PINNED = "1"
    $env:PYTHONPATH = $GuardRoot
    $env:PYTHONSAFEPATH = "1"
    $env:PYTHONNOUSERSITE = "1"
    Remove-Item Env:PYTHONHOME, Env:PYTHONSTARTUP -ErrorAction SilentlyContinue
    $env:QUANT_LEDGER_ROOT = $RepoRoot
    $env:QUANT_PINNED_PYTHON = $py
    $env:QUANT_GUARD_ROOT = $GuardRoot
    $env:GIT_CONFIG_PARAMETERS = "'core.hooksPath=NUL' 'core.fsmonitor=false' 'core.pager=' 'diff.external='"
    $probe = (@(& $py -c "import sys, json; print(json.dumps([bool(getattr(sys.flags, 'safe_path', False)) and bool(getattr(sys, '_quant_pinned_fence', False))] + sys.path))" 2>$null) -join '')
    $sp = @(); try { $sp = @(ConvertFrom-Json -InputObject $probe) } catch { $sp = @() }
    $rootLow = $RepoRoot.TrimEnd('\').ToLowerInvariant() + '\'
    $leak = @($sp | Select-Object -Skip 1 | Where-Object { "$_" -eq '' -or ("$_".TrimEnd('\') + '\').ToLowerInvariant().StartsWith($rootLow) })
    if ($sp.Count -lt 1 -or $sp[0] -ne $true -or $leak.Count -gt 0) {
        "$((Get-Date).ToUniversalTime().ToString('u')) adopt-and-seal: -Pinned python is not isolated from $RepoRoot; not adopting: $probe"
        exit 2
    }
} else {
    $py = Join-Path $RepoRoot ".venv\Scripts\python.exe"; $pyArgs = @()
    if (-not (Test-Path $py)) {
        if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py"; $pyArgs = @("-3") }
        elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
        else { "$((Get-Date).ToUniversalTime().ToString('u')) adopt-and-seal: no python interpreter found (.venv, py, python)"; exit 2 }
    }
}

# EVERY LINE ALSO GOES TO A FILE, BECAUSE A SCHEDULED TASK'S STDOUT GOES NOWHERE (2026-09-14).
#
# THIS SCRIPT IS THE BOX'S ONLY CODE-DELIVERY PATH and its sole failure report was the exit code
# `schtasks` records. Measured today: MT5-AdoptRelease sat at `Last Result: 1` across consecutive
# hours while the box silently ran code older than the branch -- and the one instruction in
# CLAUDE.md for this case, "if the box is not adopting, that task is the first thing to check",
# had nothing to check. Every reason this script can fail (a partial adoption, a lost mutex, no
# interpreter, a refused seal) was written to a stdout that no scheduled run has.
#
# Appending is deliberate: the interesting question is never "what happened on the last run" but
# "when did this start failing", and only a history answers it. Failing to write the log NEVER
# fails the adoption -- an unwritable log is a lost diagnostic, not a reason to stop delivering
# code to a live trading box.
# THE BOX TREE'S LOG, not this script's folder (adopt_once audit MF1): a run from a release
# checkout (-GuardRoot) must leave its lines where plumbing_watchdog and the freshness fence read.
# For the scheduled task $RepoRoot is three levels above this script, so the path is unchanged.
$script:AdoptLog = Join-Path $RepoRoot "desks\mt5\logs\adopt_and_seal.log"
try {
    $null = New-Item -ItemType Directory -Force -Path (Split-Path $script:AdoptLog) -ErrorAction Stop
} catch { $script:AdoptLog = $null }

function Log([string] $m) {
    $line = "$((Get-Date).ToUniversalTime().ToString('u')) adopt-and-seal: $m"
    if ($script:AdoptLog) {
        try { Add-Content -Path $script:AdoptLog -Value $line -Encoding utf8 -ErrorAction Stop } catch { }
    }
    $line
}

# ---- THE HEARTBEAT: A RUN THAT WAS KILLED MUST NOT READ LIKE A RUN THAT NEVER STARTED --------
#
# MEASURED 2026-09-24, and it is the whole reason this file gained an artifact.
#
# `MT5-AdoptRelease` runs HOURLY with `MultipleInstances = IgnoreNew` and carried
# `ExecutionTimeLimit = PT50M`. A cold adoption does not fit in fifty minutes: the individual-path
# retry below re-scans a 24,000-path worktree per pathspec, and the run waits on MT5-ShadowSync
# and the git-writer mutex before it even begins. So the box lived in a loop with two codes and
# no diagnosis:
#
#     2147946720 == 0x800710E0 == Win32 4320, "The operator or administrator has refused the
#                   request"  -- recorded with TaskScheduler event id 322, "did not launch ...
#                   because an instance of the same task is already running". The `operator` is
#                   the scheduler's own IgnoreNew policy refusing the NEXT hour.
#     267014     == 0x41306, SCHED_S_TASK_TERMINATED -- the PT50M limit killing the run that
#                   was still working.
#
# Every run long enough to finish was killed, and every run that might have replaced it was
# refused. Neither code is produced by a line of this script, and the kill lands BETWEEN
# statements: `Log` had written "waiting for MT5-ShadowSync" and nothing else, so the log of a
# killed run is INDISTINGUISHABLE from the log of a run still in progress.
#
# (The obvious reading was wrong and cost time, so it is written down: 0x800710E0 is NOT
# 0x80070520/1312 "a specified logon session does not exist". 0x80070520 is 2147943712, a
# different number, and ZERO tasks on this box carried it. Of the 31 tasks showing 0x800710E0,
# thirty ran as SYSTEM/ServiceAccount, which has no logon session to lose.)
#
# The fix is the cheapest possible: stamp `started_at` when the run begins and `finished_at` when
# it ends. A run that was killed or refused leaves the first and never the second, which is a
# POSITIVE fact an hourly fence can read (`scripts/check_adoption_freshness.py`) instead of
# inferring absence. Failing to write the heartbeat NEVER fails the adoption -- an unwritable
# artifact is a lost diagnostic, not a reason to stop delivering code to a live trading box.
$script:Heartbeat = Join-Path $desk "reports\ADOPTION_HEARTBEAT.json"
$script:StartedAt = (Get-Date).ToUniversalTime().ToString('o')
$script:HeadBefore = ""
try { $script:HeadBefore = (git -C $RepoRoot rev-parse HEAD 2>$null | Out-String).Trim() } catch { }

function Write-Heartbeat([hashtable] $fields) {
    try {
        $null = New-Item -ItemType Directory -Force -Path (Split-Path $script:Heartbeat) -ErrorAction Stop
        $base = @{
            started_at  = $script:StartedAt
            head_before = $script:HeadBefore
            branch      = $Branch
            pid         = $PID
            host        = $env:COMPUTERNAME
        }
        if ($script:ReleaseGate) { $base["release_gate"] = $script:ReleaseGate }
        foreach ($k in $fields.Keys) { $base[$k] = $fields[$k] }
        ($base | ConvertTo-Json -Depth 4) | Set-Content -Path $script:Heartbeat -Encoding utf8 -ErrorAction Stop
    } catch { }
}

# EVERY EXIT GOES THROUGH HERE. `exit` inside a scheduled PowerShell run leaves no trace of its
# own; a stage name and a code do. `stage` is the answer to "how far did it get", which is the
# question the days of silence actually needed answered.
function Done([int] $code, [string] $stage) {
    $headAfter = ""
    try { $headAfter = (git -C $RepoRoot rev-parse HEAD 2>$null | Out-String).Trim() } catch { }
    # OUR OWN WITNESS ONLY, and only once the helper has been dotted -- the early exits happen
    # before that. A witness left behind by THIS pid would read STALE the moment we exit, which
    # is true but noisy; one left by anybody else is the evidence that names the real holder.
    if (Get-Command Clear-GitWriterWitness -ErrorAction SilentlyContinue) { Clear-GitWriterWitness }
    Write-Heartbeat @{
        finished_at = (Get-Date).ToUniversalTime().ToString('o')
        exit_code   = $code
        stage       = $stage
        ok          = ($code -eq 0)
        head_after  = $headAfter
    }
    exit $code
}

Write-Heartbeat @{ finished_at = $null; exit_code = $null; stage = "started"; ok = $false }


# ------------------------------------------- 0. never adopt under a ShadowSync that is running
# TWO GIT WRITERS IN ONE REPOSITORY IN THE SAME SECOND (2026-09-08). MT5-ShadowSync repeats every
# fifteen minutes from :05 -- :05, :20, :35, :50 -- and this task was registered at :20 on the
# comment "after the :05 slot". In that second the sync runs `git checkout -- <path>` on every
# dirty incoming path (REVERTING Adopt-Release's in-place writes), a probe merge and its abort, a
# real merge, and stages its allowlist + `git commit` (which sweeps whatever Adopt-Release has
# chunk-staged into a "shadow state sync" commit that then carries CODE); Adopt-Release meanwhile
# runs status/add/commit/diff/cat-file/add/commit/merge. Whichever loses `.git/index.lock` throws:
# for Adopt-Release that is Invoke-Git -> exit 1 -> this script exits without sealing, and the
# gateway keeps refusing new risk on the old seal for another hour. The task now runs at :12; this
# guard covers a sync still inside its ten-minute limit, and the first manual run. Get-ScheduledTask
# is read-only and answers from a Limited token. Nine minutes: the sync's own limit is ten.
$waited = 0
while ((Get-ScheduledTask -TaskName "MT5-ShadowSync" -ErrorAction SilentlyContinue).State -eq "Running") {
    if ($waited -ge 540) { Log "MT5-ShadowSync still running after 9 min; not adopting under it"; Done 6 "wait-shadowsync" }
    if ($waited -eq 0) { Log "MT5-ShadowSync is running; waiting for it before adopting" }
    Start-Sleep -Seconds 5
    $waited += 5
}

# THE LOCK EVERY GIT WRITER ON THIS BOX TAKES (2026-09-08). The task-state wait above covers the
# MT5-ShadowSync task; it cannot see `hourly_cycle.publish_state`, which launches the same sync
# script directly, nor a hand run. sync_shadow_to_git.ps1 now holds the named mutex
# Local\MT5-GitWriter for its whole pass, so this script takes the same mutex BEFORE adopting and
# keeps it through the seal commit: Adopt-Release is a child process, but the lock is ours, and
# the sync yields on it. An abandoned mutex (a writer that died holding it) is a grant, not a
# wedge. Nine minutes, as above.
# AND A MUTEX WE COULD NOT CREATE IS NOT A MUTEX SOMEBODY ELSE HOLDS (2026-09-15).
#
# `New-Object System.Threading.Mutex` throws UnauthorizedAccessException when the named object
# already exists and the caller's token cannot open it with default rights -- which is exactly the
# case here: the scheduled tasks run under S4U principals and an interactive/SSH session does not.
# The throw left $script:GitWriterMutex NULL, `.WaitOne()` then failed non-terminating with
# InvokeMethodOnNull, $gotLock stayed $false, and the script reported
#
#     "another git writer holds Local\MT5-GitWriter after 9 min; not adopting under it"
#
# having waited zero seconds and having no idea whether anyone held it. The refusal was right and
# the reason was invented -- the same shape as "the terminal connection is gone", which was also
# a guess this desk printed as fact. An operator reading the log is sent to look for a phantom
# writer, and the number 9 is a lie about a wait that never happened.
# THE MUTEX IS CREATED WITH A DACL EVERY PRINCIPAL CAN OPEN (GitWriterMutex.ps1, 2026-09-23):
# a name created under one principal and unopenable by the next is a lock that stops the
# desk instead of ordering it, and that is exactly what happened for four days.
. (Join-Path $PSScriptRoot "GitWriterMutex.ps1")
$mutexHandle = Open-GitWriterMutex
$script:GitWriterMutex = $mutexHandle.Mutex
$mutexWhy = $mutexHandle.Why
$gotLock = $false
if ($null -eq $script:GitWriterMutex) {
    Log ("could not OPEN Local\MT5-GitWriter (" + $mutexWhy + ") -- this is not evidence that " +
         "another writer holds it; the lock could not be examined at all. Not adopting.")
    Done 6 "mutex-unopenable"
}
try { $gotLock = $script:GitWriterMutex.WaitOne(540000) }
catch [System.Threading.AbandonedMutexException] { $gotLock = $true }
if (-not $gotLock) {
    # NAME THE HOLDER, OR SAY THAT IT COULD NOT BE NAMED (2026-09-24). "another git writer held
    # it" was the whole message, and it is not a diagnosis: it cannot distinguish a live adoption
    # making progress from a witness left by a process that is gone. The witness file carries the
    # pid and the start time; `Get-GitWriterHolder` reports whether that pid is ALIVE. A dead
    # holder is now impossible to mistake for a live one, in the log and in the fence.
    $holder = Get-GitWriterHolder
    Log ("another git writer held the lock for the full 9 min; not adopting under it -- " + $holder.Summary)
    Done 6 "mutex-held"
}
Write-GitWriterWitness -Script "Adopt-And-Seal.ps1" -Name $mutexHandle.Name
# HEAD AS THE LOCK FOUND IT (2026-10-28). The value read at the top predates up to nine minutes of
# waiting for the sync and the mutex, and a writer that held them may have moved HEAD. A rollback
# goes back to THIS commit, so it is read again now that nobody else can move it.
try { $script:HeadBefore = (git -C $RepoRoot rev-parse HEAD 2>$null | Out-String).Trim() } catch { }
if (-not $script:HeadBefore) { Log "cannot read HEAD under the lock"; Done 2 "head-before-unreadable" }

# ------------------------------------------------ 0a. THE GUARD, AND A STALE HOLD HEALED FIRST
$script:GuardScript = Join-Path $RepoRoot "scripts\adopt_guard.py"
# THE DECIDERS FROM A RELEASE CHECKOUT (manual runs only; see .PARAMETER GuardRoot). Both scripts
# take --root, so they read and write this box's tree, never the checkout's. A checkout with any
# local change is refused before either runs: the code that decides must be the commit it names.
$script:GuardRootArgs = @()
$script:GuardHead = $null
$script:DeciderRoot = $RepoRoot
if ($GuardRoot) {
    $guardDir = $null
    try { $guardDir = (Resolve-Path -LiteralPath $GuardRoot -ErrorAction Stop).Path } catch { }
    if (-not $guardDir -or -not (Test-Path (Join-Path $guardDir "scripts\adopt_guard.py"))) {
        Log "GUARD ROOT $GuardRoot has no scripts\adopt_guard.py; not adopting"
        Done 8 "guard-root-missing"
    }
    $grDirty = @(git -C $guardDir status --porcelain --untracked-files=no 2>$null | Where-Object { "$_" -match '\S' })
    $script:GuardHead = (git -C $guardDir rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $script:GuardHead -notmatch '^[0-9a-f]{40}$' -or $grDirty.Count -gt 0) {
        Log ("GUARD ROOT {0} is not a clean checkout (head '{1}', {2} changed path(s)); not adopting" -f $guardDir, $script:GuardHead, $grDirty.Count)
        Done 8 "guard-root-unclean"
    }
    # RELEASED CODE ONLY, BEFORE IT RUNS ANYTHING (adopt_once audit SF1): heal and state-verify
    # run from here before the release gate, so the checkout must already be inside production
    # (the ref ci.yml's promote job fast-forwards), which adopt_once fetches into the checkout.
    # A pinned checkout is the owner's own install (install_guard.ps1), which is the stronger
    # warrant: it need not sit inside production.
    if (-not $Pinned) { & git -C $guardDir merge-base --is-ancestor $script:GuardHead "refs/remotes/origin/production" 2>$null }
    if (-not $Pinned -and $LASTEXITCODE -ne 0) {
        Log ("GUARD ROOT head {0} is not inside origin/production in {1}; not adopting" -f $script:GuardHead.Substring(0, 12), $guardDir)
        Done 8 "guard-root-not-released"
    }
    $script:GuardScript = Join-Path $guardDir "scripts\adopt_guard.py"
    $script:GuardRootArgs = @("--root", $RepoRoot)
    $script:DeciderRoot = $guardDir
    Log ("GUARD ROOT (manual run): guard and release gate from {0} at {1}, against {2}" -f $guardDir, $script:GuardHead.Substring(0, 12), $RepoRoot)
}
$script:Adopted = $false
$script:Recycled = $false
# THIS RUN'S NAME ON ITS HOLD (adopter v3 audit MF1): a "nothing was adopted" exit lifts only the
# hold this run placed, never one a failed rollback left standing.
$script:RunId = [guid]::NewGuid().ToString("N")
# The code roots release.seal refuses to seal over (libs.ops.adopt_guard.CODE_ROOTS is the same list).
$releaseCodePaths = @(
    "desks/mt5/mt5desk", "desks/mt5/prop", "desks/mt5/research",
    "desks/mt5/policy", "desks/mt5/scripts", "libs", "ops", "scripts", "pyproject.toml"
)
# CODE ON DISK THAT DIFFERS FROM HEAD after Adopt-Release: never sealed over, never lifted over.
function Get-DirtyCode {
    return @(git diff --name-only --no-ext-diff HEAD -- $releaseCodePaths 2>$null |
             Where-Object { "$_" -match '\S' } | ForEach-Object { "$($_)".Trim().Trim('"') })
}
function Lift-IfClean([string] $stage) {
    $d = Get-DirtyCode
    if ($d.Count -gt 0) {
        $d | Select-Object -First 12 | ForEach-Object { Log "    $_" }
        Undo-Adoption "$($d.Count) code path(s) dirty on a nothing-to-seal exit" 3 "$stage-dirty-code"
    }
    $null = Invoke-AdoptGuard @("lift", "--run", $script:RunId)
}
# Log both writes the file and EMITS the line; inside a function an emitted line would join the
# return value, so every Log here goes to the host instead.
function Invoke-AdoptGuard([string[]] $guardArgs) {
    $out = @(& $py @pyArgs $script:GuardScript @script:GuardRootArgs @guardArgs 2>&1 | ForEach-Object { "$_" })
    $rc = $LASTEXITCODE
    $json = @($out | Where-Object { $_ -match '^\s*\{' }) | Select-Object -Last 1
    $doc = $null
    if ($json) { try { $doc = $json | ConvertFrom-Json } catch { $doc = $null } }
    $why = if ($doc -and $doc.reason) { [string]$doc.reason } else { ($out | Select-Object -Last 2) -join ' | ' }
    $decision = if ($doc -and $doc.decision) { [string]$doc.decision } else { "ERROR" }
    Log ("adopt guard {0}: exit {1} {2} -- {3}" -f $guardArgs[0], $rc, $decision, $why) | Out-Host
    return @{ Code = $rc; Doc = $doc; Decision = $decision; Why = $why }
}
# THE WAY BACK. `rollback` puts up the new-risk hold before it writes a byte (every lane stops
# OPENING; management, cancels and flattens keep running) and pages if it fails. A resident that
# was asked to recycle, or restarted on its own during the adoption, imported the bad code, so it
# is recycled again; then the restored release must pass the same health check, and only that
# lifts the hold. Unhealthy after the rollback: the hold stays, the guard pages, exit 12.
function Undo-Adoption([string] $why, [int] $code, [string] $stage) {
    if (-not $script:Adopted) { Done $code $stage }
    $rb = Invoke-AdoptGuard @("rollback", "--to", $script:HeadBefore, "--bad", $gateTarget, "--why", $why)
    if ($rb.Code -ne 0) {
        Log "ROLLBACK FAILED; new risk held on every lane until a healthy run; paged: $($rb.Why)" | Out-Host
        Done 12 "$stage-rollback-failed"
    }
    Log ("rolled back to {0}: {1}" -f $script:HeadBefore.Substring(0, 12), $why) | Out-Host
    $loaded = "0"
    try { $loaded = ((& $py @pyArgs $script:GuardScript @script:GuardRootArgs loaded-since --since $script:StartedAt 2>$null) | Select-Object -Last 1).Trim() } catch { }
    $expect = "0"
    $rbAt = (Get-Date).ToUniversalTime().ToString('o')
    if ($script:Recycled -or $loaded -eq "1") {
        New-Item -ItemType File -Path (Join-Path $desk "data\GATEWAY_RECYCLE") -Force | Out-Null
        Start-ScheduledTask -TaskName "MT5-GatewayResident" -ErrorAction SilentlyContinue
        $expect = $script:GatewayExpected
    }
    $after = Invoke-AdoptGuard @("health", "--sealed-at", "HEAD", "--since", $rbAt, "--gateway-expected", $expect, "--page-on-fail")
    if ($after.Code -ne 0) {
        Log "the restored release is not healthy either; new risk stays held; paged" | Out-Host
        Done 12 "$stage-rolled-back-unhealthy"
    }
    Done $code "$stage-rolled-back"
}
# THE BOX'S SWITCHES, TOO (adopter v4; zuck 2026-10-28 06:43Z: no typed word for a live change).
# A switch committed under desks/mt5/data/box_state_desired/ with an auditor CLEAR (today:
# GOLD_OCO_MODE.json) is written to the box's live copy by libs/ops/desired_state.py, once per
# committed version, outside the gold windows, and stays provisional -- put back by itself by
# state-verify -- until a gold window has run on it.
# Called on every exit where the running release is the sealed one; it never changes the exit.
function Invoke-StateApply {
    $st = Invoke-AdoptGuard @("state-apply")
    if ($st.Code -ne 0 -and $st.Code -ne 10) { Log "box-state apply: $($st.Decision) -- $($st.Why)" | Out-Host }
}
if (-not (Test-Path $script:GuardScript)) {
    Log "adopt guard absent in this tree (scripts\adopt_guard.py); keeping the running release"
    Done 8 "adopt-guard-absent"
}
# A GATEWAY IS EXPECTED when one was passing before this run OR its task is not disabled: a
# resident that was down at the start is still supposed to come back on the new code.
$gatewayWasAlive = "0"
try { $gatewayWasAlive = ((& $py @pyArgs $script:GuardScript @script:GuardRootArgs gateway-alive 2>$null) | Select-Object -Last 1).Trim() } catch { }
$script:GatewayExpected = $gatewayWasAlive
if ($script:GatewayExpected -ne "1") {
    $gr = Get-ScheduledTask -TaskName "MT5-GatewayResident" -ErrorAction SilentlyContinue
    if ($gr -and [string]$gr.State -ne "Disabled") { $script:GatewayExpected = "1" }
}
# A HOLD AN EARLIER RUN LEFT UP comes down here the moment the running release looks healthy (one
# look, no wait); a person's hold is never touched. FIRST, straight after the mutex (adopter v3
# audit MF2): the release-gate hold and error exits below used to run before it, so a hold left by
# a killed run stood -- and never paged -- for as long as the gate kept holding.
$null = Invoke-AdoptGuard @("heal", "--gateway-expected", $script:GatewayExpected)
# A PROVISIONAL BOX SWITCH IS WATCHED EVERY RUN, the gold windows included: it only ever puts the
# old switch back (a lane failed on it, or a lane it added went silent and froze gold everywhere).
$null = Invoke-AdoptGuard @("state-verify")

# ------------------------------------------------ 0b. THE RELEASE GATE: ONLY GREEN CODE LANDS
# 2026-09-30. Until today this box adopted the branch TIP, so a commit CI had not finished
# judging -- or had judged red (7379cbf7 edited the sealed gauntlet and the law gate went red
# while the tip sat there for the next hourly adoption) -- became live code within the hour.
# `release_promotion.py gate` fetches the tip and the `production` pointer that ci.yml's promote
# job fast-forwards after BOTH gates are green, and decides:
#
#   ADOPT_TIP      the tip is a green release plus seal/state commits (the usual case: the box's
#                  own quarter-hourly pushes sit on top of the release) -> adopt the tip
#   ADOPT_RELEASE  the tip carries code no green run has released -> adopt the release instead
#   HOLD           ... and this box already runs that release -> nothing to adopt; wait for CI
#   HOLD           no verifiable tested release exists -> keep the running code
#   OVERRIDE_TIP   -AllowUnreleased / ADOPT_UNRELEASED / QUANT_ADOPT_UNRELEASED -> the tip
#
# FAIL CLOSED: a missing, failed, malformed or unrecognised gate never becomes permission
# to adopt an untested branch tip. Retry through the scheduled path after the defect clears.
$script:ReleaseGate = $null
$gateTarget = $null
$gateScript = Join-Path $script:DeciderRoot "scripts\release_promotion.py"
if (Test-Path $gateScript) {
    $gateArgs = @($gateScript, "gate", "--branch", $Branch, "--root", $RepoRoot)
    if ($AllowUnreleased) { $gateArgs += "--allow-unreleased" }
    $gateOut = @(& $py @pyArgs @gateArgs 2>&1 | ForEach-Object { "$_" })
    $gateExit = $LASTEXITCODE
    $gate = $null
    $gateJson = @($gateOut | Where-Object { $_ -match '^\s*\{' }) | Select-Object -Last 1
    if ($gateJson) { try { $gate = $gateJson | ConvertFrom-Json } catch { $gate = $null } }
    if ($gateExit -eq 0 -and $gate -and $gate.decision) {
        $script:ReleaseGate = @{ decision = [string]$gate.decision; target = [string]$gate.target
                                 reason = [string]$gate.reason; tip = [string]$gate.tip
                                 release_ref = [string]$gate.release_ref }
        Log ("release gate: {0} -- {1}" -f $gate.decision, $gate.reason)
        if ($gate.decision -eq "HOLD") {
            $n = @($gate.unreleased_code).Count
            Log ("holding: {0} unreleased code path(s) on the tip, first: {1}" -f $n,
                 ((@($gate.unreleased_code) | Select-Object -First 6) -join ', '))
            Done 0 "held-awaiting-release"
        }
        if ($gate.decision -notin @("ADOPT_TIP", "ADOPT_RELEASE", "OVERRIDE_TIP") -or -not $gate.target) {
            Log "release gate returned no recognised adoption authority; keeping the running release"
            Done 8 "release-gate-invalid"
        }
        $gateTarget = [string]$gate.target
    } else {
        $why = if ($gate -and $gate.reason) { [string]$gate.reason } else { ($gateOut | Select-Object -Last 3) -join ' | ' }
        $script:ReleaseGate = @{ decision = "ERROR"; reason = $why }
        Log ("release gate could not decide (exit {0}): {1} -- keeping the running release" -f $gateExit, $why)
        Done 8 "release-gate-error"
    }
} else {
    $script:ReleaseGate = @{ decision = "ABSENT"; reason = "scripts\release_promotion.py not in this tree" }
    Log "release gate absent in this tree (scripts\release_promotion.py); keeping the running release"
    Done 8 "release-gate-absent"
}

# ------------------------------------------------- 0b. AUDITED CODE ONLY, NEVER NEAR A TRADE
# THE ADOPTER RAN ON "CI IS GREEN" ALONE (2026-10-28), so it sat disabled and adoption went back to
# a laptop sitting -- and the night that sitting stalled, the E8/FTMO/Fusion gold trade the fix was
# for was missed. `scripts/adopt_guard.py` (libs/ops/adopt_guard.py has the rules) adds what the
# desk's own rules ask of a release and the release gate cannot see:
#
#     pre       every governed path the target changes (code, scripts, money-path config) carries
#               content an auditor CLEAR row in desks/mt5/data/ADOPT_CLEARS.jsonl vouches for, no
#               HOLD revokes it, none of it was rolled back before, and the BROKER clock is clear
#               of every gold window's blackout (asia, london_am, afternoon) with the margin a
#               cold adoption needs
#     smoke     after the in-place write, before the seal: the live entry modules import and
#               prestart_check.py (when the box has one) says start
#     health    after the seal and recycle: the release identity allows new risk under the new
#               seal, a resident gateway started after the recycle stamps that seal and a finished
#               pass, and no live lane task failed since
#
# and on ANY failure after the first byte is written, puts the code back to the commit this run
# started from (an accepted seal a minute ago) by itself, under a new-risk hold that every lane
# obeys and only a passing health check lifts. A guard that cannot run keeps the running release.
# A GUARD ROOT DECIDES ONLY FOR CODE IT IS PART OF: its commit must be an ancestor of (or be) the
# target, so the guard that vouches is never newer than, or foreign to, the release it lets in.
if ($script:GuardHead) {
    & git -C $RepoRoot merge-base --is-ancestor $script:GuardHead $gateTarget 2>$null
    if ($LASTEXITCODE -ne 0) {
        Log ("GUARD ROOT head {0} is not an ancestor of the target {1}; not adopting" -f $script:GuardHead.Substring(0, 12), $gateTarget.Substring(0, 12))
        Done 8 "guard-root-not-in-target"
    }
}
$pre = Invoke-AdoptGuard @("pre", "--target", $gateTarget)
if ($pre.Code -eq 10) {
    $held = switch ($pre.Decision) {
        "HOLD_BLACKOUT"    { "held-blackout" }
        "HOLD_ROLLED_BACK" { "held-rolled-back" }
        default            { "held-awaiting-audit" }
    }
    foreach ($p in @($pre.Doc.uncovered) + @($pre.Doc.rolled_back) | Where-Object { $_ } | Select-Object -First 12) {
        Log "    $p"
    }
    Done 0 $held
}
if ($pre.Code -ne 0) { Done 8 "adopt-guard-error" }

# ---------------------------------------------------------------- 1. adopt the branch's tree
# NEXT TO THIS SCRIPT FIRST, then the repository's copy. The two ship together and the mutex
# helper is already dotted from $PSScriptRoot, so resolving one of the three from $RepoRoot and
# the other two from beside the file was an inconsistency waiting to bite. It also makes the
# pair RUNNABLE FROM OUTSIDE THE TREE (`-RepoRoot C:\opt\quant` from a staging directory), which
# is the only way to test a change to the adoption against the live repository without first
# committing that change into the very repository the adoption is about to overwrite.
$adoptScript = Join-Path $PSScriptRoot "Adopt-Release.ps1"
if (-not $Pinned -and -not (Test-Path $adoptScript)) { $adoptScript = Join-Path $desk "scripts\Adopt-Release.ps1" }
if (-not (Test-Path $adoptScript)) { Log "Adopt-Release.ps1 missing at $adoptScript"; Done 2 "adopt-script-missing" }
# THE CONSOLE IS KEPT, BECAUSE THE ONE LINE BELOW IS NOT A DIAGNOSIS (2026-09-23). For four days
# this log said "Adopt-Release exited 1 -- partial adoption" once an hour and named nothing; the
# paths, the index.lock fatals and the chunk retries all went to a scheduled task's stdout, which
# is discarded. A deployment path that cannot say WHY it failed is the same defect this desk keeps
# finding one level up: activity reported, outcome withheld. An unwritable console log is a lost
# diagnostic, never a reason to stop delivering code, so the tee is best-effort.
$adoptConsole = Join-Path $desk "logs\adopt_release_console.log"
# TEE, NOT COLLECT-THEN-WRITE. Buffering the whole console and writing it at the end gives an
# operator nothing while the pass runs -- and a pass that HANGS (five hours of one, measured
# 2026-09-23) would then write nothing at all, which is the exact failure this capture exists to
# end. Tee-Object writes each line as it arrives AND passes it down the pipeline, so the array
# below still holds everything for the log excerpt.
try {
    Set-Content -Path $adoptConsole -Encoding utf8 -ErrorAction Stop `
        -Value ("{0} Adopt-Release start branch={1}" -f (Get-Date).ToUniversalTime().ToString('o'), $Branch)
} catch { $adoptConsole = $null }
# The verified gate choice is mandatory; it already fetched the immutable target.
$adoptArgs = @("-RepoRoot", $RepoRoot, "-Branch", $Branch)
$adoptArgs += @("-Target", $gateTarget, "-NoFetch")
# THE HOLD GOES UP BEFORE THE FIRST BYTE (adopter v2 audit MF2). The E8 and FTMO lanes import from
# disk on every run and never ask the release identity, so a run killed between here and the
# health check (the task's time limit) would leave them trading a half-written tree. Every lane
# opens nothing while it stands; health or a later run's heal lifts it, and a heal that still
# finds it after 90 minutes pages. Billed as a veto (adopt_new_risk_hold). No hold, no adoption.
# ONLY WHEN SOMETHING GOVERNED CHANGES (adopter v3 audit MF3): most hours the target is the running
# release plus state commits, and holding every lane through that Adopt-Release bought nothing.
# A missing answer holds. A failure without a hold still rolls back, and the rollback holds first.
if ($pre.Doc -and $pre.Doc.needs_hold -eq $false) {
    Log "no governed path changes; adopting without the new-risk hold"
} else {
    $hold = Invoke-AdoptGuard @("hold", "--run", $script:RunId, "--why", ("adopting {0} over {1}" -f $gateTarget.Substring(0, 12), $script:HeadBefore.Substring(0, 12)))
    if ($hold.Code -ne 0) { Log "the new-risk hold could not be written; not adopting"; Done 8 "hold-unwritable" }
}
# FROM HERE ON A BYTE MAY BE WRITTEN, so every failure below goes back through Undo-Adoption.
$script:Adopted = $true
if ($adoptConsole) {
    $adoptOut = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adoptScript `
        @adoptArgs 2>&1 |
        ForEach-Object { "$_" } | Tee-Object -FilePath $adoptConsole -Append)
} else {
    $adoptOut = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adoptScript `
        @adoptArgs 2>&1 | ForEach-Object { "$_" })
}
$adoptExit = $LASTEXITCODE
# EXIT 7 IS A REFUSAL, NOT A PARTIAL ADOPTION: Adopt-Release found the fetched target's judge
# unsealed and wrote nothing. The running release and its gateway stay as they are.
if ($adoptExit -eq 7) {
    foreach ($line in @($adoptOut | Where-Object { $_ -match 'target seal|REFUSING target|changed since signing|not in the signed|unreadable' } | Select-Object -First 16)) {
        Log ("    " + $line.Trim())
    }
    Log "target judge is not sealed; nothing adopted, current release kept"
    $null = Invoke-AdoptGuard @("lift", "--run", $script:RunId)
    Done 7 "target-unsealed"
}
if ($adoptExit -ne 0) {
    Log "Adopt-Release exited $adoptExit -- partial adoption; NOT sealing a tree that only half-matches the branch"
    # THE PATHS, IN THIS LOG, NOW. `desks/mt5/reports/ADOPTION_STATE.json` carries the full list
    # for plumbing_watchdog; the operator reading this file gets the first dozen without having
    # to know the artifact exists.
    # FROM THE REFUSAL ONWARD, not every indented line in the console. The console also lists
    # the state paths that are explicitly NOT blocking, and a filter that swept those in put
    # twelve harmless ledger names into the log under a line about a failed adoption -- evidence
    # that points away from the cause is worse than none.
    $refusalAt = [Array]::FindIndex([string[]]$adoptOut, [Predicate[string]] {
        param($l) $l -match 'REFUSING to record|could not be written or unlinked' })
    $excerpt = if ($refusalAt -ge 0) { @($adoptOut[$refusalAt..($adoptOut.Count - 1)]) }
               else { @($adoptOut | Where-Object { $_ -match '\[FAIL\]|index\.lock|did not stage' }) }
    foreach ($line in @($excerpt | Where-Object { $_ -match '\S' } | Select-Object -First 16)) {
        Log ("    " + $line.Trim())
    }
    Log "full console: desks/mt5/logs/adopt_release_console.log; paths: desks/mt5/reports/ADOPTION_STATE.json"
    Undo-Adoption "Adopt-Release exited $adoptExit (partial adoption)" $adoptExit "adopt-release-partial"
}

# The released reader requires an explicit state handoff: ordinary adoption preserves box state.
$ledgerMigration = Join-Path $script:DeciderRoot "scripts\migrate_live_ledger_view.py"
if (Test-Path -LiteralPath $ledgerMigration) {
    $migrationOut = @(& $py @pyArgs $ledgerMigration --target $gateTarget --apply 2>&1 |
                     ForEach-Object { "$_" })
    $migrationExit = $LASTEXITCODE
    foreach ($line in $migrationOut) { Log ("ledger handoff: " + $line) }
    if ($migrationExit -ne 0) {
        Log "ledger handoff failed; refusing to seal an incomplete adoption"
        Undo-Adoption "ledger handoff exited $migrationExit" $migrationExit "ledger-handoff-failed"
    }
}

# ------------------------------------------- 1a. THE NEW CODE MUST RUN, AND NOT INTO A WINDOW
# Checked BEFORE the seal: until the seal moves, release_identity refuses new risk on the adopted
# tree, so a failure here costs minutes of no new risk and is undone before it costs a trade.
$headNow = (git rev-parse HEAD 2>$null | Out-String).Trim()
if ($headNow -and $headNow -ne $script:HeadBefore) {
    $smoke = Invoke-AdoptGuard @("smoke")
    if ($smoke.Code -ne 0) { Undo-Adoption ("smoke: " + $smoke.Why) 11 "smoke-failed" }
    # Thirty minutes of margin: the seal, the recycle and the health wait still follow.
    $clock = Invoke-AdoptGuard @("blackout", "--margin-min", "30")
    if ($clock.Code -ne 0) { Undo-Adoption ("ran into a trade window: " + $clock.Why) 0 "blackout" }
}

# ------------------------------------- 1b. TASKS THE ADOPTED TREE DECLARES BUT THE BOX LACKS
# A task with an installer in the repo and no registration on the box is code that runs nowhere
# (III.16). MT5-FrontierAudit was exactly that: declared daily in box_tasks.manifest, installer
# NONE, thirty organs scheduled only by one machine's memory. Each installer here is called with
# -IfMissing, so a registered task is NEVER touched (re-registering live tasks has failed with
# "Access is denied") and a missing one appears on the first adoption after it ships. Best-effort:
# a failed registration is logged and never stops the seal.
# FTMO trades every certified sleeve (principal 2026-11-03 / 11-05; Governance ruling 2026-11-05):
# the book's solve on its own clock and the sleeve executor, which stays STANDBY until
# data\FTMO_EXECUTOR_ARMED exists. Registering either arms nothing.
foreach ($ensure in @(
        @{ Task = "MT5-FTMO-Allocator"; Installer = "install_ftmo_allocator_task.ps1" },
        @{ Task = "MT5-FTMO-Executor"; Installer = "install_ftmo_executor_task.ps1" },
        @{ Task = "MT5-FrontierAudit"; Installer = "install_frontier_audit_task.ps1" })) {
    if (Get-ScheduledTask -TaskName $ensure.Task -ErrorAction SilentlyContinue) { continue }
    # (C4) the installers live in the tree; the pinned adopter never runs them as SYSTEM.
    if ($Pinned) { Log "ensure-task: $($ensure.Task) missing; not installed under -Pinned (tree installer)"; continue }
    $installer = Join-Path $desk ("scripts\" + $ensure.Installer)
    if (-not (Test-Path $installer)) { Log "ensure-task: $($ensure.Task) missing and $installer absent"; continue }
    try {
        $out = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installer -IfMissing 2>&1 |
                 ForEach-Object { "$_" })
        Log ("ensure-task: {0} was missing; installer exit {1}: {2}" -f $ensure.Task, $LASTEXITCODE, ($out -join ' | '))
    } catch {
        Log ("ensure-task: {0} registration failed: {1}" -f $ensure.Task, $_.Exception.Message)
    }
}

# ------------------------------------------------------------ 2a. the box's release signing key
# EVERY RELEASE.json THIS BOX EVER WROTE WAS UNSIGNED (measured 2026-09-30): `release.seal` signs
# only when data/secrets/release_signing.key exists, and nothing ever created it. `ensure_key`
# creates it ONCE and never overwrites; only its file name is logged, never its bytes. The key is
# gitignored and never leaves this box. Best-effort: a failure here is logged, the seal goes on
# (unsigned, with the reason written into the record).
$keyOut = @(& $py @pyArgs -c "import sys; from pathlib import Path; from libs.ops import release_signing as rs; created, msg = rs.ensure_key(Path(sys.argv[1])); print(msg)" $RepoRoot 2>&1 |
            ForEach-Object { "$_" })
Log ("signing key: exit {0}: {1}" -f $LASTEXITCODE, ($keyOut -join ' | '))

# SIGN THE RELEASE THE BOX IS ALREADY RUNNING. The two "nothing to seal" exits below are the ones
# every hour takes, so a record sealed before the key existed would stay unsigned until the next
# code change. `release.ensure_signed` signs it in place ONLY when HEAD is accepted and the money
# path and judge core on disk match the record; it never commits and never raises, and nothing
# here lets its answer change the exit code.
function Ensure-Signed {
    try {
        $out = @(& $py @pyArgs -c "import sys; from pathlib import Path; from libs.ops import release; d = release.ensure_signed(root=Path(sys.argv[1])); print(d.get('state'), '-', d.get('why'))" $RepoRoot 2>&1 |
                 ForEach-Object { "$_" })
        Log ("ensure-signed: {0}" -f ($out -join ' | '))
    } catch {
        Log ("ensure-signed: failed to run: {0}" -f $_.Exception.Message)
    }
}

# ------------------------------------------------ 1b. the box's stuck steps, healed as SYSTEM
# The ROOT pin at the wrong path, a jammed gate clone and stale bin copies used to each wait for
# a person in an elevated window. ops\box\box_selfheal.ps1 says what each step will and will not
# do; every step acts only on its exact stuck shape and never stops the seal.
$selfheal = Join-Path $RepoRoot "ops\box\box_selfheal.ps1"
if ($Pinned) {
    Log "selfheal: skipped under -Pinned (box_selfheal.ps1 lives in the tree)"
} elseif (Test-Path $selfheal) {
    try { . $selfheal; Invoke-BoxSelfHeal } catch { Log "selfheal: could not load: $($_.Exception.Message)" }
}

# ------------------------------------------------------ 2. seal, only if HEAD is not sealed
$head = (git rev-parse HEAD 2>$null | Out-String).Trim()
if (-not $head) { Log "cannot read HEAD"; Undo-Adoption "HEAD unreadable after adoption" 2 "head-unreadable" }
$sealed = ""
if (Test-Path $release) {
    try { $sealed = [string](Get-Content $release -Raw | ConvertFrom-Json).code_sha } catch { $sealed = "" }
}
if ($sealed -eq $head) {
    Log "HEAD $($head.Substring(0,12)) is already the sealed code; nothing to do"
    Ensure-Signed
    Lift-IfClean "already-sealed"   # the code is the sealed code: nothing was adopted
    Invoke-StateApply
    Done 0 "already-sealed"
}
# A SEAL COMMIT OR A STATE-SYNC COMMIT ON TOP OF THE SEALED CODE IS THE SAME RELEASE. After the
# first seal HEAD is the seal commit itself, and every quarter-hour sync moves it again, so
# "sealed != head" is true for the rest of time; taken literally it re-sealed and re-committed
# RELEASE.json every hour forever. `release.accepts` is the rule the gateway itself applies
# (the SHA differs only by seal/state paths), so it is the rule here too.
if ($sealed) {
    $acc = & $py @pyArgs -c "import sys; from pathlib import Path; from libs.ops import release; r = Path(sys.argv[2]); ok, why, _ = release.accepts(sys.argv[1], release.load(r) or {}, root=r); print('OK' if ok else 'NO'); print(why)" $head $RepoRoot 2>$null
    if ("$acc" -match '^OK') {
        Log "HEAD $($head.Substring(0,12)) is the sealed release $($sealed.Substring(0,12)) plus seal/state commits only; nothing to seal"
        Ensure-Signed
        Lift-IfClean "accepts-nothing-to-seal"   # state only: no code was adopted
        Invoke-StateApply
        Done 0 "accepts-nothing-to-seal"
    }
}
# `release.seal` refuses a tree with a dirty CODE path. Say so HERE, with the paths, rather than
# let a Python traceback be the only record. Untracked files (??) are not dirt; a tracked STATE
# path is not dirt either -- on this box every organ rewrites its artifact between syncs, so a
# ledger is dirty for most of every hour by design, and a check that refused on it could only
# ever seal in the seconds after a sync (it never did). The same prefixes
# `libs.ops.release.STATE_PREFIXES` names, and `release.seal` applies the same rule itself.
# ($releaseCodePaths is defined in 0a, beside Get-DirtyCode, which needs it first.)
# A BUILD ARTIFACT IS NOT CODE DRIFT, AND COUNTING IT REFUSED EVERY SEAL FOREVER (2026-09-24).
# `dist/quant-platform.zip` is REGENERATED by the build, so it differs from HEAD on every pass by
# construction. Measured on the box: Adopt-Release's own `code_drift` reads 0 while this check
# counted that one path, so every run adopted the tree, landed its merge, and then exited 3 with
# "refusing to seal: 1 tracked code path(s) differ". TWO DEFINITIONS OF CODE DRIFT IN ONE
# PIPELINE, disagreeing on exactly one file, and the disagreement was permanent.
#
# It is listed here rather than added to the state prefixes on purpose: `dist/` is not desk STATE
# and must not start being treated as such by `release.seal` too. It is build output, which is a
# third category -- neither code to protect nor state to carry.
# Do not run full ``git status`` here.  On the trading box that re-stats 28,000+ evidence paths
# while holding the release mutex and is the direct cause of index.lock collisions.  Inspect the
# code roots only; this is the same refusal boundary Adopt-Release applies before writing.
$dirty = @(git diff --name-only --no-ext-diff HEAD -- $releaseCodePaths 2>$null |
           Where-Object { "$_" -match '\S' } | ForEach-Object { "$($_)".Trim().Trim('"') })
if ($dirty.Count -gt 0) {
    Log "refusing to seal: $($dirty.Count) tracked code path(s) differ from HEAD after adoption:"
    $dirty | Select-Object -First 12 | ForEach-Object { Log "    $_" }
    Undo-Adoption "$($dirty.Count) code path(s) dirty after adoption" 3 "dirty-code-path"
}
& $py @pyArgs -c "import sys; from pathlib import Path; from libs.ops import release; d=release.seal(root=Path(sys.argv[1]), by='Adopt-And-Seal'); print(d.get('code_sha') or d.get('live_sha'))" $RepoRoot
if ($LASTEXITCODE -ne 0) { Log "release.seal failed (exit $LASTEXITCODE)"; Undo-Adoption "release.seal failed" 4 "seal-failed" }

# --------------------------------------------- 3. RELEASE.json alone -- the pure-seal commit
git add -- "desks/mt5/data/RELEASE.json"
if ($LASTEXITCODE -ne 0) { Log "seal stage failed (exit $LASTEXITCODE)"; Undo-Adoption "seal stage failed" 5 "seal-stage-failed" }

# `git commit` repeatedly crashed with 0xC0000005 on the trading box while refreshing its
# 28,000+ path Windows index.  The index already contains the adopted HEAD plus this one staged
# state file, so build the same pure commit with Git plumbing and advance the branch atomically.
# This also avoids hooks touching unrelated runtime state.  Refuse rather than guess if another
# path was staged by a concurrent writer or HEAD is detached.
$staged = @(git diff --cached --name-only --no-ext-diff 2>$null |
            Where-Object { "$_" -match '\S' } | ForEach-Object { "$($_)".Trim().Trim('"') })
if ($LASTEXITCODE -ne 0 -or $staged.Count -ne 1 -or $staged[0] -ne "desks/mt5/data/RELEASE.json") {
    Log "seal commit refused: staged paths are not exactly RELEASE.json: $($staged -join ', ')"
    Undo-Adoption "seal stage contaminated" 5 "seal-stage-contaminated"
}
$branchRef = (git symbolic-ref -q HEAD 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $branchRef) {
    Log "seal commit refused: HEAD is detached or branch ref is unreadable"
    Undo-Adoption "branch unreadable at seal" 5 "seal-branch-unreadable"
}
$tree = (git write-tree 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $tree) { Log "seal write-tree failed"; Undo-Adoption "seal write-tree failed" 5 "seal-write-tree-failed" }
$message = "Seal release $($head.Substring(0,12)) (Adopt-And-Seal, unattended)"
$sealCommit = (git commit-tree $tree -p $head -m $message 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $sealCommit) {
    Log "seal commit-tree failed (exit $LASTEXITCODE)"
    Undo-Adoption "seal commit-tree failed" 5 "seal-commit-tree-failed"
}
git update-ref $branchRef $sealCommit $head
if ($LASTEXITCODE -ne 0) {
    Log "seal update-ref refused; HEAD changed concurrently"
    Undo-Adoption "seal update-ref refused" 5 "seal-update-ref-failed"
}
Log "pure seal commit $($sealCommit.Substring(0,12)) created by atomic commit-tree/update-ref"

# ---------------------------------------- 4. the gateway reads the seal at start; restart it
# THE RESIDENT IS ASKED, NOT KILLED (2026-09-16). MT5-Gateway is disabled; the sole pass runner
# is MT5-GatewayResident, which recycles itself between passes when this marker exists. Starting
# the task is the backstop for a resident that is not running (the singleton makes it a no-op
# otherwise). The gate attestation re-tests the sealed sha at once so tested_sha never lags.
$recycledAt = (Get-Date).ToUniversalTime().ToString('o')
New-Item -ItemType File -Path (Join-Path $desk "data\GATEWAY_RECYCLE") -Force | Out-Null
Start-ScheduledTask -TaskName "MT5-GatewayResident" -ErrorAction SilentlyContinue
$script:Recycled = $true
Start-ScheduledTask -TaskName "MT5-GateAttest" -ErrorAction SilentlyContinue

# ------------------------------------------- 5. THE ONE BIT, RECORDED BY THE ACT THAT SEALS
# Tier-1 B1: "may this code create new exposure". The seal, the gate attestation and the runtime
# drift check each held a piece and nothing joined them, so `tested_sha` read UNMEASURED for
# weeks while the gates were green. `release_authority` joins all three on the CODE TREE -- the
# only subject that survives a box committing its own ledgers on top of the code it runs -- and
# publishing it HERE makes the seal and the bit one act rather than two hopes.
#
# IT REPORTS, IT DOES NOT REFUSE. Refusing to seal without a green attestation was the obvious
# next step and it is the wrong one: the tree is already adopted in place by the time this runs,
# so an unsealed tree means `release_identity` refuses NEW risk on every gateway pass -- a halt
# bought from a slow or unrelated-red gate. That reduces the book by fiat, which the principal's
# standing order (2026-09-08) forbids. The bit is measured, logged and published; turning it
# into a veto is the principal's call, not this script's.
if ($Pinned) {
    Log "release authority: under -Pinned the hourly leg publishes it (the script lives in the tree)"
} else {
    & $py @pyArgs (Join-Path $desk "research\release_authority.py") --once 2>&1 | ForEach-Object { Log "  $_" }
}

# ------------------------------------------------ 6. THE NEW RELEASE MUST BE THE ONE RUNNING
# The identity must run under the seal of $head, the code just sealed (not HEAD, which the box's
# own state commits move); an expected gateway must restart after the recycle, stamp that seal
# and finish a pass; and no live lane may have failed on it. A pass lifts any hold of ours.
$hl = Invoke-AdoptGuard @("health", "--sealed", $head, "--since", $recycledAt, "--gateway-expected", $script:GatewayExpected)
if ($hl.Code -ne 0) { Undo-Adoption ("health: " + $hl.Why) 11 "unhealthy" }
Log "sealed $($head.Substring(0,12)) from $Branch; resident asked to recycle; gate attestation triggered"
Invoke-StateApply
Done 0 "sealed"
