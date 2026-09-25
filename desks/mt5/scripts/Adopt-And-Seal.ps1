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
#>
param(
    [string] $RepoRoot,
    [string] $Branch = "claude/llm-auto-upgrade-verify-gcjac3"
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
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"; $pyArgs = @()
if (-not (Test-Path $py)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py"; $pyArgs = @("-3") }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
    else { "$((Get-Date).ToUniversalTime().ToString('u')) adopt-and-seal: no python interpreter found (.venv, py, python)"; exit 2 }
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
$script:AdoptLog = Join-Path $PSScriptRoot "..\logs\adopt_and_seal.log"
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

# ---------------------------------------------------------------- 1. adopt the branch's tree
# NEXT TO THIS SCRIPT FIRST, then the repository's copy. The two ship together and the mutex
# helper is already dotted from $PSScriptRoot, so resolving one of the three from $RepoRoot and
# the other two from beside the file was an inconsistency waiting to bite. It also makes the
# pair RUNNABLE FROM OUTSIDE THE TREE (`-RepoRoot C:\opt\quant` from a staging directory), which
# is the only way to test a change to the adoption against the live repository without first
# committing that change into the very repository the adoption is about to overwrite.
$adoptScript = Join-Path $PSScriptRoot "Adopt-Release.ps1"
if (-not (Test-Path $adoptScript)) { $adoptScript = Join-Path $desk "scripts\Adopt-Release.ps1" }
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
if ($adoptConsole) {
    $adoptOut = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adoptScript `
        -RepoRoot $RepoRoot -Branch $Branch 2>&1 |
        ForEach-Object { "$_" } | Tee-Object -FilePath $adoptConsole -Append)
} else {
    $adoptOut = @(& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adoptScript `
        -RepoRoot $RepoRoot -Branch $Branch 2>&1 | ForEach-Object { "$_" })
}
$adoptExit = $LASTEXITCODE
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
    Done $adoptExit "adopt-release-partial"
}

# ------------------------------------------------------ 2. seal, only if HEAD is not sealed
$head = (git rev-parse HEAD 2>$null | Out-String).Trim()
if (-not $head) { Log "cannot read HEAD"; Done 2 "head-unreadable" }
$sealed = ""
if (Test-Path $release) {
    try { $sealed = [string](Get-Content $release -Raw | ConvertFrom-Json).code_sha } catch { $sealed = "" }
}
if ($sealed -eq $head) {
    Log "HEAD $($head.Substring(0,12)) is already the sealed code; nothing to do"
    Done 0 "already-sealed"
}
# A SEAL COMMIT OR A STATE-SYNC COMMIT ON TOP OF THE SEALED CODE IS THE SAME RELEASE. After the
# first seal HEAD is the seal commit itself, and every quarter-hour sync moves it again, so
# "sealed != head" is true for the rest of time; taken literally it re-sealed and re-committed
# RELEASE.json every hour forever. `release.accepts` is the rule the gateway itself applies
# (the SHA differs only by seal/state paths), so it is the rule here too.
if ($sealed) {
    $acc = & $py @pyArgs -c "import sys; from libs.ops import release; ok, why, _ = release.accepts(sys.argv[1], release.load() or {}); print('OK' if ok else 'NO'); print(why)" $head 2>$null
    if ("$acc" -match '^OK') {
        Log "HEAD $($head.Substring(0,12)) is the sealed release $($sealed.Substring(0,12)) plus seal/state commits only; nothing to seal"
        Done 0 "accepts-nothing-to-seal"
    }
}
# `release.seal` refuses a tree with a dirty CODE path. Say so HERE, with the paths, rather than
# let a Python traceback be the only record. Untracked files (??) are not dirt; a tracked STATE
# path is not dirt either -- on this box every organ rewrites its artifact between syncs, so a
# ledger is dirty for most of every hour by design, and a check that refused on it could only
# ever seal in the seconds after a sync (it never did). The same prefixes
# `libs.ops.release.STATE_PREFIXES` names, and `release.seal` applies the same rule itself.
$statePrefixes = @("desks/mt5/data/", "desks/mt5/reports/", "desks/mt5/logs/",
                   "desks/mt5/frontier_intel/data/", "desks/mt5/side_channels/data/",
                   "data/", "reports/", "logs/", "web/", "docs/")  # mirror libs/ops/release.py STATE_PREFIXES
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
$buildArtifacts = @("dist/")
$dirty = @(git status --porcelain --untracked-files=no 2>$null | Where-Object { $_ } | ForEach-Object {
    $p = ("$_".Substring(3) -split ' -> ')[-1].Trim().Trim('"') -replace '\\', '/'
    $isState = $false
    foreach ($prefix in $statePrefixes) { if ($p.StartsWith($prefix)) { $isState = $true; break } }
    foreach ($prefix in $buildArtifacts) { if ($p.StartsWith($prefix)) { $isState = $true; break } }
    if (-not $isState) { $p }
})
if ($dirty.Count -gt 0) {
    Log "refusing to seal: $($dirty.Count) tracked code path(s) differ from HEAD after adoption:"
    $dirty | Select-Object -First 12 | ForEach-Object { Log "    $_" }
    Done 3 "dirty-code-path"
}
& $py @pyArgs -c "from libs.ops import release; d=release.seal(by='Adopt-And-Seal'); print(d.get('code_sha') or d.get('live_sha'))"
if ($LASTEXITCODE -ne 0) { Log "release.seal failed (exit $LASTEXITCODE)"; Done 4 "seal-failed" }

# --------------------------------------------- 3. RELEASE.json alone -- the pure-seal commit
git add -- "desks/mt5/data/RELEASE.json"
git commit -q -m "Seal release $($head.Substring(0,12)) (Adopt-And-Seal, unattended)"
if ($LASTEXITCODE -ne 0) { Log "seal commit failed (exit $LASTEXITCODE)"; Done 5 "seal-commit-failed" }

# ---------------------------------------- 4. the gateway reads the seal at start; restart it
# THE RESIDENT IS ASKED, NOT KILLED (2026-09-16). MT5-Gateway is disabled; the sole pass runner
# is MT5-GatewayResident, which recycles itself between passes when this marker exists. Starting
# the task is the backstop for a resident that is not running (the singleton makes it a no-op
# otherwise). The gate attestation re-tests the sealed sha at once so tested_sha never lags.
New-Item -ItemType File -Path (Join-Path $desk "data\GATEWAY_RECYCLE") -Force | Out-Null
Start-ScheduledTask -TaskName "MT5-GatewayResident" -ErrorAction SilentlyContinue
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
& $py @pyArgs (Join-Path $desk "research\release_authority.py") --once 2>&1 | ForEach-Object { Log "  $_" }
Log "sealed $($head.Substring(0,12)) from $Branch; resident asked to recycle; gate attestation triggered"
Done 0 "sealed"
