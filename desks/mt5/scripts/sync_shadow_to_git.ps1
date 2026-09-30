# sync_shadow_to_git.ps1 -- replaces sync_shadow_to_vps.ps1 as the cross-brain visibility path.
#
# WHY THIS EXISTS. Hetzner (quant@95.216.191.70, /home/quant/quant-platform) was fully
# decommissioned 2026-08-23: it was still running the retired native-crypto desk's own cron jobs
# and a systemd unit alongside serving as the sole destination for the old scp-based shadow sync,
# so killing the crypto side meant killing the sync destination too. Every brain (Claude, Codex,
# OpenCode, DeepSeek) already reads/writes the SAME git branch, so that is the new transport: no
# VPS, no ssh host-key hazard, no scp "lost connection" debugging. sync_shadow_to_vps.ps1 is left
# in place, unwired, in case Hetzner-style sync is ever needed again -- see its own header.
#
# WHAT TRAVELS. Only the small, machine-overwritten state summaries every brain needs to answer
# "is Contabo healthy, is it armed, what's live" -- never the data lake, never anything under
# data/secrets. Each is individually allowlisted in .gitignore for exactly this reason.
#
# SAFETY (R0423: never share a worktree with another live session). This commits ONLY the exact
# paths below -- never `git add -A`, never `git commit -a`, never `git stash` -- so any other
# session's uncommitted work in this same checkout is never touched. A push rejection is resolved
# by fetch + merge (never rebase, never stash) exactly as docs/AGENTS.md prescribes for a shared
# tree; a genuine conflict aborts the merge and reports rather than guessing.

$ErrorActionPreference = "Stop"
$DeskRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent (Split-Path -Parent $DeskRoot)
$log = Join-Path $DeskRoot "logs\sync_shadow_to_git.log"

function Write-SyncLog($msg) {
    $line = "{0} {1}" -f (Get-Date -Format "o"), $msg
    # Write-Output becomes a function return value in PowerShell. Merge-FetchHead returns a
    # boolean, so a diagnostic line plus `$false` became a truthy two-item array and callers logged
    # "merged" after a refusal. Host output remains visible to Task Scheduler without contaminating
    # any function's result channel.
    Write-Host $line
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
        Add-Content -Path $log -Value $line -Encoding utf8
    } catch {}
}

function Git-In-Repo {
    param([string[]] $GitArgs)
    # DISCARD GIT'S OUTPUT, RETURN ONLY THE EXIT CODE.
    #
    # A PowerShell function returns its ENTIRE output stream, not just what `return` names. So
    # `& git ...` writing "[claude/llm-auto-upgrade-verify-gcjac3 9ab483e9b17] mt5 shadow state
    # sync" to stdout made that string part of the return value, and the caller's `if ($rc -ne 0)`
    # was true for every SUCCESSFUL commit. Measured 2026-09-03, the log read
    #
    #     ABORT: git commit failed rc=[claude/... 9ab483e9b17] mt5 shadow state sync 2026-09-03_082
    #
    # every fifteen minutes -- on commits that had LANDED. The script aborted immediately after
    # committing and therefore never reached the push, so 616 commits accumulated on the box and
    # were never published. This file's own header calls itself "the cross-brain visibility path";
    # it had been committing into a hole for as long as the bug existed, and the alarm it raised
    # said the opposite of what was wrong.
    #
    # Piping to Out-Null leaves $LASTEXITCODE intact -- it is git's real exit status -- while
    # keeping the function's output stream empty, which is what makes `return` mean what it says.
    # ErrorActionPreference is "Stop" for this script, and under Stop a native command writing to
    # STDERR raises NativeCommandError -- so merging git's streams would turn its ordinary
    # "warning: LF will be replaced by CRLF" into a fatal error. git reports failure through its
    # EXIT CODE, which is the only thing this function claims to return, so its chatter is
    # discarded on both streams and Stop is restored immediately afterwards.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & git -C $RepoRoot @GitArgs 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prev
    }
    return $LASTEXITCODE
}

# YIELD TO AN ADOPTION IN PROGRESS (2026-09-08). MT5-AdoptRelease rewrites the tree in place and
# commits by name; this pass would `git checkout -- <path>` its dirty incoming paths (undoing the
# adoption's writes), race it for `.git/index.lock`, and sweep its chunk-staged code into a
# "shadow state sync" commit. The adoption is the rarer and more consequential writer, so this
# pass steps aside: the next slot is fifteen minutes away and nothing here is lost by waiting.
# The adoption task has the mirror guard (it waits out a running sync before it starts).
$adopting = $false
try {
    $adopting = ((Get-ScheduledTask -TaskName "MT5-AdoptRelease" -ErrorAction SilentlyContinue).State -eq "Running")
} catch { $adopting = $false }
if ($adopting) {
    Write-SyncLog "SKIP: MT5-AdoptRelease is adopting; this pass yields (next slot in 15 min)"
    exit 0
}

# ONE GIT WRITER AT A TIME, BY PROCESS, NOT BY TASK NAME (2026-09-08, after a verifier read the
# guard above and found its blind spot). This script has a second invoker that is not the
# MT5-ShadowSync task: `hourly_cycle.publish_state` launches it directly, and a hand run under
# box-repair is a third. A guard keyed on Task Scheduler state sees none of those, and the
# adoption's mirror guard cannot see them either. A named mutex is held by whichever PROCESS owns
# it, whoever launched it, and the operating system releases it when that process exits -- so a
# crashed writer never wedges the lock (the next waiter receives it as ABANDONED, which is a
# grant). Two minutes covers a full sync pass; a writer that cannot get the lock in that time
# yields exactly as the task check above yields, and the next slot is fifteen minutes away.
. (Join-Path $PSScriptRoot "GitWriterMutex.ps1")
# THE WHOLE HANDLE, NOT JUST `.Mutex` (2026-09-23). Taking `.Mutex` drops the LEGACY name the
# helper also acquires, so a writer still running pre-2026-09-23 code was not coordinated with at
# all; and when the helper cannot open ANY name, `.Mutex` is $null, `$null.WaitOne()` fails
# non-terminating under `Continue`, `$gotLock` stays $false and this pass yields blaming a writer
# nobody measured. That exact confusion -- a refusal with an invented reason -- is what kept the
# adoption from running for four days.
$script:GitWriterHandle = Open-GitWriterMutex
$script:GitWriterMutex = $script:GitWriterHandle.Mutex
if ($null -eq $script:GitWriterMutex) {
    Write-SyncLog ("SKIP: could not OPEN the git-writer lock (" + $script:GitWriterHandle.Why +
                   ") -- this is not evidence that another writer holds it; the lock could not " +
                   "be examined at all")
    exit 0
}
$gotLock = $false
try { $gotLock = $script:GitWriterMutex.WaitOne(120000) }
catch [System.Threading.AbandonedMutexException] { $gotLock = $true }
if (-not $gotLock) {
    Write-SyncLog ("SKIP: another git writer held " + $script:GitWriterHandle.Name +
                   " for the full 2 min; this pass yields")
    exit 0
}

# PARK THE DIRTY FILES THAT BLOCK THE MERGE, MERGE, PUT THEM BACK. One function, two callers.
#
# It was inlined in the push-rejection retry loop, which is the only place that ever fetched --
# so hoisting a pre-push fetch meant either duplicating this or extracting it. Duplicated merge
# logic on the tree that places trades is how the two copies drift and one of them starts
# guessing at a resolution, so it is extracted.
#
# git refuses to merge when incoming commits touch a file with local modifications, and this box
# rewrites hundreds of tracked artifacts continuously. Measured 2026-09-03: 376 files were dirty
# and 60 were incoming, but the OVERLAP -- the only thing actually blocking the merge -- was TWO:
# desks/mt5/data/sync_marker.json and desks/mt5/data/universe/universe.json. Neither is on this
# sync's allowlist, so it never commits them, so they are dirty forever and every merge failed
# forever. `git merge-tree` reported the merge itself as CLEAN; nothing was in conflict but the
# working tree. The cost was 616 commits sitting unpushed on this box, unseen by every other
# brain, while this file's own header calls itself the cross-brain visibility path.
#
# The local copies are COPIED ASIDE, not stashed (R0423 forbids `git stash` in a shared tree) and
# not discarded -- universe.json is a protected registry whose records may not vanish. After the
# merge they are restored byte-for-byte, so the working tree ends exactly as it began and the
# only thing that changed is that the merge could run.
#
# Returns $true on a clean merge, $false on conflict (caller decides whether that is fatal).
function Merge-FetchHead {
    param([string]$RepoRoot, [string]$Branch)
    # Let Git's native unpack-tree preflight name the actual blockers. This is the only bounded
    # method on the multi-million-path box: per-incoming-path status exploded subprocess count;
    # a whole-tree diff took more than four minutes; even 128-path batches timed out when an
    # incoming discovery commit named tens of thousands of artifacts. The merge preflight already
    # computes exactly the two lists we need, using Git's index-native implementation.
    # UNTRACKED FILES BLOCK A MERGE TOO, AND PARKING TRACKED ONES DOES NOTHING FOR THEM.
    #
    # git raises TWO separate refusals and this only ever handled the first:
    #     error: Your local changes to the following files would be overwritten by merge
    #     error: The following untracked working tree files would be overwritten by merge
    # The second fires when the incoming branch has begun tracking a path this box already holds
    # as an untracked local file -- which is every artifact a new organ started writing here
    # before its producer was committed upstream. MEASURED 2026-09-06 on the desk box: 50 such
    # paths, including the entire data/hypotheses docket.
    #
    # The log said `push rejected (attempt 1), fetch+merge and retry` and then STOPPED -- no
    # merge line, no abort line, nothing -- roughly 800 consecutive times since 2026-08-26. The
    # box committed locally every fifteen minutes and published none of it, and the one line that
    # would have named the cause was never written. A failure path that logs nothing is why this
    # ran for eleven days in plain sight.
    #
    # The box's copy is moved aside rather than deleted: for the data artifacts it is the LIVE
    # state and strictly newer than anything on the branch. It is restored below exactly like the
    # tracked ones, so the merge can run and the box keeps what it had.
    # THE SAME `Stop` + `2>&1` TRAP `Git-In-Repo` GUARDS AGAINST, AND THIS CALL NEEDS IT MOST.
    # The probe exists to make the merge FAIL and read the list of untracked files out of the
    # failure text -- so stderr output is the expected, load-bearing result, not an anomaly.
    # Under `ErrorActionPreference = "Stop"` the first stderr line becomes a terminating
    # NativeCommandError, which kills the pass at precisely the moment the probe succeeds at its
    # job, and the parking logic below never runs. Relaxed only around the call.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        # The trading checkout may enable merge.autoStash globally. A preflight must never
        # snapshot the multi-gigabyte runtime tree: it only needs Git's native overlap check.
        $probe = @(& git -C $RepoRoot -c merge.autoStash=false merge --no-commit --no-ff FETCH_HEAD 2>&1 |
                   ForEach-Object { "$_" })
        $probeRc = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    Git-In-Repo @("merge", "--abort") | Out-Null
    $blockers = @()
    $untracked = @()
    $list = ""
    foreach ($line in $probe) {
        $s = "$line"
        if ($s -match "local changes to the following files would be overwritten") {
            $list = "tracked"
            continue
        }
        if ($s -match "untracked working tree files would be overwritten") {
            $list = "untracked"
            continue
        }
        if ($list) {
            if ($s -match "^\s+(\S.*)$") {
                if ($list -eq "tracked") { $blockers += $Matches[1].Trim() }
                else { $untracked += $Matches[1].Trim() }
            } else {
                $list = ""
            }
        }
    }
    if ($probeRc -ne 0 -and -not $blockers.Count -and -not $untracked.Count) {
        $probeSummary = (($probe | Select-Object -First 8) -join " | ")
        Write-SyncLog ("merge probe found a genuine conflict or Git refusal, not a parsed " +
                       "dirty-tree blocker: " + $probeSummary)
        return $false
    }

    $parked = @{}
    foreach ($rel in $blockers) {
        $full = Join-Path $RepoRoot ($rel -replace "/", "\")
        if (Test-Path $full -PathType Leaf) {
            $tmp = [System.IO.Path]::GetTempFileName()
            Copy-Item -LiteralPath $full -Destination $tmp -Force
            $parked[$rel] = $tmp
            Git-In-Repo @("checkout", "--", $rel) | Out-Null
        }
    }
    foreach ($rel in $untracked) {
        $full = Join-Path $RepoRoot ($rel -replace "/", "\")
        if (Test-Path $full -PathType Leaf) {
            $tmp = [System.IO.Path]::GetTempFileName()
            Copy-Item -LiteralPath $full -Destination $tmp -Force
            $parked[$rel] = $tmp
            Remove-Item -LiteralPath $full -Force -ErrorAction SilentlyContinue
        }
    }
    if ($untracked.Count) {
        Write-SyncLog ("parked {0} untracked file(s) the incoming branch now tracks" -f $untracked.Count)
    }

    if ($parked.Count) {
        Write-SyncLog ("parked {0} file(s) that block the merge: {1}" -f `
                       $parked.Count, (($parked.Keys | Select-Object -First 8) -join ", "))
    }

    $mergeRc = Git-In-Repo @("merge", "--no-edit", "FETCH_HEAD")

    foreach ($rel in $parked.Keys) {
        $full = Join-Path $RepoRoot ($rel -replace "/", "\")
        Copy-Item -LiteralPath $parked[$rel] -Destination $full -Force
        Remove-Item -LiteralPath $parked[$rel] -Force -ErrorAction SilentlyContinue
    }
    if ($mergeRc -ne 0) {
        Write-SyncLog "merge conflict against FETCH_HEAD (origin/$Branch) -- aborting merge, leaving the work local for a human"
        Git-In-Repo @("merge", "--abort") | Out-Null
        return $false
    }
    return $true
}



# THE PUBLISHER MAY NOT DELETE RESEARCH INPUTS. On 2026-09-28 `Get-PSDrive C` returned a
# transient 0-byte reading while the volume was being enlarged. This function believed it and
# deleted 1,731 bar files even though the resized volume then exposed 903+ GB free. The hourly
# universe task was also unable to see the interactive MT5 terminal, so 823 forward clocks were
# left with seven charts between them. "Refetchable" is not the same as "safe to delete": bars
# are the evidence surface while refetch is only a future possibility.
#
# Disk reclamation belongs to `reclaim_disk.py`, which measures derived caches, duplicate rows
# and protected data explicitly. A Git publisher has one authority: publish. If disk is below
# its floor it records the blocker and lets the next pass retry; it never changes the data plane.
function Free-DiskForGit {
    param([string]$RepoRoot, [double]$FloorGB = 1.5)
    $free = (Get-PSDrive C).Free / 1GB
    if ($free -ge $FloorGB) { return }
    Write-SyncLog ("DISK BLOCKER: $([math]::Round($free,2))GB free (floor ${FloorGB}GB). " +
                   "Publisher left every bar/tick/evidence file untouched; reclaim_disk owns " +
                   "measured cleanup and this pass may fail/retry.")
}

# CODE ADOPTION HAS ONE OWNER. The publisher used to merge FETCH_HEAD itself. On the trading
# box a large merge outlived Task Scheduler's ten-minute limit: PowerShell was terminated,
# released the named mutex, and left its child `git merge` running against `.git/index.lock`.
# MT5-AdoptRelease then acquired the mutex legitimately and collided with that orphan. The
# publisher owns runtime-state publication; MT5-AdoptRelease owns inbound code and sealing.
# Keeping those authorities separate makes a timeout recoverable instead of corrupting the next
# writer's window.
$script:InboundAdoptionRequired = $false
function Request-Adoption {
    param([string]$Branch, [string]$Reason)
    $script:InboundAdoptionRequired = $true
    Write-SyncLog ("DEFER: origin/$Branch requires canonical adoption ($Reason); " +
                   "publisher will not merge code or hold the git-writer lock through adoption")
    try {
        $task = Get-ScheduledTask -TaskName "MT5-AdoptRelease" -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            Write-SyncLog "WARN: MT5-AdoptRelease task is absent; inbound code remains pending"
        } elseif ($task.State -eq "Running") {
            Write-SyncLog "MT5-AdoptRelease is already running"
        } else {
            Start-ScheduledTask -TaskName "MT5-AdoptRelease"
            Write-SyncLog "requested MT5-AdoptRelease"
        }
    } catch {
        Write-SyncLog ("WARN: could not request MT5-AdoptRelease: " + $_.Exception.Message)
    }
}

# THE PULL, AND IT RUNS BEFORE EVERY EARLY EXIT. See Sync-Pull's caller near the top of the run.
function Sync-Pull {
    param([string]$RepoRoot, [string]$Branch)
    Write-SyncLog "pulling origin/$Branch (delivery must not depend on having something to say)"
    Free-DiskForGit -RepoRoot $RepoRoot
    $rc = Git-In-Repo @("fetch", "origin", $Branch)
    if ($rc -ne 0) {
        # A STALE REMOTE-TRACKING REF IS RECOVERABLE AND USED TO STOP THE SYNC DEAD. Measured
        # 2026-09-07: `error: cannot lock ref 'refs/remotes/origin/<branch>': is at 2fb56f78 but
        # expected 81e2ed3d`. Two fetches raced -- this task runs every fifteen minutes and a
        # person was pulling by hand -- so the ref had ALREADY advanced to the commit being
        # fetched and git refused to write the update it no longer needed to write. The desired
        # state was reached and reported as a failure.
        #
        # `--prune` rewrites the tracking refs from what the remote actually has, which is exactly
        # the disagreement here, so one retry through it clears both the race and a tracking ref
        # left stale by an earlier interrupted fetch. Still non-fatal if it fails again.
        Write-SyncLog "fetch failed rc=$rc -- retrying with --prune (stale or raced tracking ref)"
        $rc = Git-In-Repo @("fetch", "--prune", "origin", $Branch)
    }
    if ($rc -ne 0) {
        # A FAILED FETCH IS NOT A REASON TO ABORT THE SYNC. The local state is still worth
        # committing and pushing, and the push-rejection path fetches again. Degrading to the old
        # behaviour beats trading a delivery bug for an availability one.
        Write-SyncLog "WARN: fetch failed rc=$rc after retry -- continuing; the push path still fetches on rejection"
        return
    }
    $behind = @(& git -C $RepoRoot rev-list --count "HEAD..FETCH_HEAD") | Select-Object -First 1
    if (-not $behind -or [int]$behind -eq 0) { Write-SyncLog "up to date with origin/$Branch"; return }
    Request-Adoption -Branch $Branch -Reason "$behind inbound commit(s)"
}

# PUBLISH THE BOX'S STATE WITHOUT MERGING CODE (2026-09-30).
#
# MEASURED: no box-authored state commit has reached this branch since 2026-09-25, and the
# shadow lane files on it still carry `updated_at: 2026-09-16`. Since ff281c49b this publisher
# hands inbound code to MT5-AdoptRelease and EXITS whenever origin is ahead -- before staging
# anything. Origin takes dozens of commits a day from the other agents, and adoption runs once
# an hour, so at almost every fifteen-minute slot the box was behind, deferred, and published
# nothing. Every reader off the box -- the CRO cycle, the audits, the dashboard -- then measured
# a frozen git copy and reported the forward engine as silent for a week.
#
# The fix keeps both authorities exactly where Codex put them. This function never merges,
# never touches the working tree, HEAD or the real index: it takes the blobs this box has just
# committed LOCALLY for its own state paths, lays them over FETCH_HEAD's tree in a PRIVATE index
# file, and pushes one commit whose only parent is origin's tip -- a fast-forward carrying
# nothing but state. Inbound code still waits for the adopter; the adopter still finds the box's
# versions of these paths in its own local commits (so its kept-by-box rule keeps them).
function Git-Lines {
    param([string[]] $GitArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = @(& git -C $RepoRoot @GitArgs 2>$null | ForEach-Object { "$_" })
        $script:GitLinesRc = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
    }
    return ,$out
}

function Publish-StateOnto {
    param([string]$RepoRoot, [string]$Branch, [string[]]$Paths)
    if (-not $Paths -or $Paths.Count -eq 0) { Write-SyncLog "publish: no state paths"; return $false }
    $entries = @(Git-Lines (@("ls-tree", "HEAD", "--") + $Paths) | Where-Object { $_ -match '\S' })
    if ($entries.Count -eq 0) {
        Write-SyncLog "publish: HEAD carries none of the state paths yet; nothing to publish"
        return $false
    }
    $idx = Join-Path ([System.IO.Path]::GetTempPath()) ("mt5-state-index-{0}" -f $PID)
    $prevIndex = $env:GIT_INDEX_FILE
    for ($try = 1; $try -le 3; $try++) {
        if ($try -gt 1) {
            $rc = Git-In-Repo @("fetch", "origin", $Branch)
            if ($rc -ne 0) { Write-SyncLog "publish: re-fetch failed rc=$rc"; return $false }
        }
        $base = (Git-Lines @("rev-parse", "FETCH_HEAD") | Select-Object -First 1)
        if (-not $base) { Write-SyncLog "publish: FETCH_HEAD unreadable"; return $false }
        $base = "$base".Trim()
        try {
            $env:GIT_INDEX_FILE = $idx
            $rc = Git-In-Repo @("read-tree", $base)
            if ($rc -ne 0) { Write-SyncLog "publish: read-tree $base failed rc=$rc"; return $false }
            $n = 0
            foreach ($line in $entries) {
                # "<mode> blob <sha>`t<path>" -- the blob the box committed, never re-read from
                # disk, so origin receives byte-for-byte what the box's own history holds.
                $meta, $rel = $line -split "`t", 2
                $f = $meta -split '\s+'
                if ($f.Count -lt 3 -or $f[1] -ne "blob") { continue }
                $rc = Git-In-Repo @("update-index", "--add", "--cacheinfo", ("{0},{1},{2}" -f $f[0], $f[2], $rel))
                if ($rc -eq 0) { $n++ }
            }
            $tree = (Git-Lines @("write-tree") | Select-Object -First 1)
        } finally {
            if ($null -eq $prevIndex) { Remove-Item Env:GIT_INDEX_FILE -ErrorAction SilentlyContinue }
            else { $env:GIT_INDEX_FILE = $prevIndex }
            Remove-Item -LiteralPath $idx -Force -ErrorAction SilentlyContinue
        }
        if (-not $tree) { Write-SyncLog "publish: write-tree failed"; return $false }
        $tree = "$tree".Trim()
        $baseTree = "$(Git-Lines @("rev-parse", "$base^{tree}") | Select-Object -First 1)".Trim()
        if ($tree -eq $baseTree) {
            Write-SyncLog "publish: origin/$Branch already carries this box state ($n path(s))"
            return $true
        }
        $stampNow = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm")
        $msg = "mt5 box state $stampNow (published onto origin; inbound code left to MT5-AdoptRelease)"
        $commit = "$(Git-Lines @("commit-tree", $tree, "-p", $base, "-m", $msg) | Select-Object -First 1)".Trim()
        if (-not $commit) { Write-SyncLog "publish: commit-tree failed"; return $false }
        $remote = "origin"
        $rc = Git-In-Repo @("push", $remote, ("{0}:refs/heads/{1}" -f $commit, $Branch))
        if ($rc -eq 0) {
            Write-SyncLog ("published box state onto origin/{0} as {1} ({2} path(s)) without merging code" -f
                           $Branch, $commit.Substring(0, 12), $n)
            return $true
        }
        Write-SyncLog "publish: push of $($commit.Substring(0, 12)) rejected (attempt $try); origin moved -- re-basing onto the new tip"
    }
    Write-SyncLog "ABORT: box state could not be published after 3 attempts"
    return $false
}

# Desk-relative paths of every state file this sync carries. Each MUST already be individually
# allowlisted in .gitignore (git add is silently a no-op on an ignored path otherwise, which
# would look like success while publishing nothing -- exactly the failure mode this script exists
# to avoid repeating).
$relPaths = @(
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/data/gateway_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/regime_state.json",
    # The release-identity verdict the gateway writes every pass: running SHA against the sealed
    # release, and whether new risk is allowed. It is the one line that answers "is the box
    # running the code that was tested" from any machine that can read this branch.
    "desks/mt5/data/release_identity.json",
    # THE LANE STATE FILES. Until 2026-09-06 the only thing that crossed this wire was the
    # 424-byte health SUMMARY, so no reader on the other side could see a single sleeve: not its
    # status, not its forward n, not its expectancy, not its day count. That is why "are the two
    # gold scalp sleeves ready for live capital" was unanswerable from the branch, and why the
    # answer kept being assembled from historical rows instead.
    #
    # A summary that says OPERATING is not evidence about any individual sleeve. Carrying the
    # rows themselves is what turns this sync from a heartbeat into a report.
    "desks/mt5/reports/shadow/scalp_shadow_state.json",
    "desks/mt5/reports/shadow/qquant_shadow_state.json",
    "desks/mt5/reports/shadow/external_shadow_state.json",
    "desks/mt5/reports/shadow/shadow_state.json",
    # The live account read. This box owns the only MT5 terminal, so it is the only machine
    # entitled to publish an equity figure -- build_zentech_state refuses to invent one without a
    # terminal, and until now had nothing to fall back on but a pulled copy of its own last
    # output.
    "desks/mt5/data/account_state.json",
    # THE ATTRIBUTION CHAIN (2026-09-08). None of these four had ever reached this branch, so
    # the chain research_id -> decision -> intent -> fill -> realised R could not be verified
    # off the box, and every counterfactual organ that reads the decision and intent ledgers
    # (counterfactual_replay, action_counterfactuals, missed_growth, execution_intelligence)
    # has reported n=0 since it was written -- not because it is wrong, because it was never
    # given an input. Small append-only JSONL the running code writes and reports/markout.json's
    # sibling; outputs of the release, never inputs that change what it does.
    "desks/mt5/data/decision_ledger.jsonl",
    "desks/mt5/data/order_intents.jsonl",
    "desks/mt5/data/live_ledger.jsonl",
    "desks/mt5/reports/attribution_chain.json"
)
# THE RESEARCH MEASUREMENTS THE DESK IS JUDGED ON (2026-09-30). The CRO cycle, the audits and the
# breadth review all read these from the branch, and none had ever been committed from the box:
# every one was "UNMEASURED" or "GIT-ONLY stale" off the box while fresh on it. Kept apart from
# $relPaths ON PURPOSE: $relPaths is pinned to release.NON_CODE (a money-path file), while every
# path here sits under desks/mt5/reports/ or desks/mt5/data/, which `release.is_state_path`
# already classifies as state -- so the seal is untouched by adding them. Each is allowlisted at
# the end of .gitignore (tests/scripts/test_box_sync_publishes_what_it_lists.py pins that), and
# each must stay a small JSON summary: a file over $ReportCapBytes is skipped and said so, never
# silently truncated and never allowed to turn this wire into a data lake.
$ReportCapBytes = 4MB
$reportPaths = @(
    "desks/mt5/reports/RESEARCH_BUDGET.json",
    "desks/mt5/data/research_budget.json",
    "desks/mt5/reports/JUDGING_RATE.json",
    "desks/mt5/reports/JUDGING_THROUGHPUT.json",
    "desks/mt5/reports/GAUNTLET_BACKPRESSURE.json",
    "desks/mt5/reports/JUDGE_COVERAGE.json",
    "desks/mt5/reports/EFFECTIVE_BREADTH.json",
    "desks/mt5/reports/BREADTH_MANDATE.json",
    "desks/mt5/reports/TIER1_SCORECARD.json",
    "desks/mt5/reports/ALT_DATA_YIELD.json",
    "desks/mt5/reports/PRODUCER_YIELD.json",
    "desks/mt5/reports/RESEARCH_PRODUCTIVITY.json",
    "desks/mt5/reports/FORWARD_ENROLMENT.json",
    "desks/mt5/reports/CERTIFICATE_CLOCK_LAW.json",
    "desks/mt5/reports/FORWARD_CLOCK_LEDGER.json",
    "desks/mt5/reports/shadow/precert_shadow_state.json",
    # THE ONE BINARY HERE, and deliberately so (2026-09-30). macro_desk.anchors() writes it
    # hourly on the box; the branch copy was last committed 2026-09-12 with T10YIE all NaN,
    # so REAL_YIELD_10Y is empty for every reader off the box and on CI. FRED is reachable
    # only from the box, so the box is the only machine that can refresh it. ~1.5 MB, a daily
    # frame that changes once a day; the cap above still applies.
    "desks/mt5/data/cross_asset_anchors.pkl"
)
$existing = @()
foreach ($rel in $relPaths) {
    $full = Join-Path $RepoRoot ($rel -replace "/", "\")
    if (Test-Path $full) { $existing += $rel }
}
foreach ($rel in $reportPaths) {
    $full = Join-Path $RepoRoot ($rel -replace "/", "\")
    if (-not (Test-Path $full -PathType Leaf)) { continue }
    $bytes = (Get-Item -LiteralPath $full).Length
    if ($bytes -gt $ReportCapBytes) {
        Write-SyncLog ("SKIP report {0}: {1:N0} bytes exceeds the {2:N0}-byte cap for this wire" -f $rel, $bytes, $ReportCapBytes)
        continue
    }
    $existing += $rel
}
# PULL FIRST, ALWAYS, BEFORE ANY EARLY EXIT (2026-09-06).
#
# THIS SCRIPT USED TO PULL ONLY BY ACCIDENT, and it needed TWO accidents at once: the box had to
# have state worth committing AND had to lose a push race, because the only fetch lived inside the
# push-rejection retry loop and both guards below exit 0 before ever reaching it. A quiet box --
# no new shadow rows this cycle -- returned at "no change since last sync" and never contacted
# origin at all. So the machine holding live capital received code only when it happened to be
# busy and unlucky.
#
# MEASURED 2026-09-06: this branch sat 41 commits behind desk-sync-clean while the box ran
# GATEWAY_FAMILY_POPULATIONS = ("hunt16",) -- 65 of 66 certificates unexecutable -- and a
# shadow_admission with no CANON_SOURCES, so nothing could enrol. Both had been fixed days
# earlier. Every CERTIFIED-NOT-ENROLLED row on the dashboard was this, not a desk defect.
#
# Pulling is now the FIRST thing the sync does and depends on nothing: not on local changes, not
# on a push, not on a rejection. Push remains conditional on having something to push, which is
# correct -- an empty commit every fifteen minutes is noise. Delivery is not.
$branch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
Sync-Pull -RepoRoot $RepoRoot -Branch $branch
# INBOUND CODE NO LONGER SILENCES THE BOX. This exited here when origin was ahead, which on a
# branch that moves every few minutes was nearly every pass, so the box's state stopped reaching
# the branch at all (see Publish-StateOnto). The adopter still owns the code; the state below is
# committed locally as always and then published onto origin's tip without a merge.

if ($existing.Count -eq 0) {
    Write-SyncLog "SKIP: none of the tracked state files exist yet on this box"
    exit 0
}

$addRc = Git-In-Repo (@("add", "--") + $existing)
if ($addRc -ne 0) { Write-SyncLog "ABORT: git add failed rc=$addRc"; exit 1 }

# Nothing changed since the last cycle -- do not create empty commits every 15 minutes forever.
& git -C $RepoRoot diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    # NOTHING NEW TO COMMIT IS NOT NOTHING TO DELIVER, and conflating the two is why this script
    # could publish nothing for eleven days while reporting the truth every fifteen minutes.
    #
    # The old path exited here. So a commit that was MADE and then failed to PUSH -- which is what
    # a full disk does, git dies mid-pack as "the remote end hung up unexpectedly" -- sat local
    # forever: every later run found the state files unchanged against that local commit, said
    # "no change since last sync", and never tried the push again. The desk had already recorded
    # its state; delivery was one retry away and nothing ever retried.
    #
    # Delivery must not depend on having something NEW to say. Same principle the pull above
    # already follows, applied to the push.
    if ($script:InboundAdoptionRequired) {
        $ok = Publish-StateOnto -RepoRoot $RepoRoot -Branch $branch -Paths $existing
        if ($ok) { exit 0 } else { exit 1 }
    }
    $ahead = (& git -C $RepoRoot rev-list --count "origin/$branch..HEAD" 2>$null)
    if ($ahead -and [int]$ahead -gt 0) {
        Write-SyncLog "no new state, but $ahead local commit(s) have never reached origin -- pushing"
        $rc = Git-In-Repo @("push", "origin", "HEAD")
        if ($rc -eq 0) { Write-SyncLog "delivered $ahead previously-unpushed commit(s)"; exit 0 }
        Write-SyncLog "ABORT: push of $ahead unpushed commit(s) failed rc=$rc -- state is committed here and NOT on the branch"
        exit 1
    }
    Write-SyncLog "no change since last sync"
    exit 0
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm")
$commitRc = Git-In-Repo @("commit", "-m", "mt5 shadow state sync $stamp")
if ($commitRc -ne 0) { Write-SyncLog "ABORT: git commit failed rc=$commitRc"; exit 1 }

$branch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
if ($script:InboundAdoptionRequired) {
    # Origin is ahead: pushing HEAD would be refused. The state commit just made stays local for
    # the adopter's kept-by-box rule, and the same blobs go up onto origin's tip now.
    $ok = Publish-StateOnto -RepoRoot $RepoRoot -Branch $branch -Paths $existing
    if ($ok) { exit 0 } else { exit 1 }
}

# PULL BEFORE PUSHING, ALWAYS -- NOT ONLY WHEN THE PUSH IS REJECTED (2026-09-06).
#
# THIS IS WHY THE BOX RAN CODE NOBODY HAD SHIPPED IT. The loop below fetches only after a push
# is REJECTED, so the box pulled purely as conflict resolution. When its push SUCCEEDS -- which
# it does whenever nobody else pushed in that same minute, i.e. almost always -- the box never
# fetched at all. Delivery to the machine that holds live capital was a side effect of losing a
# race.
#
# MEASURED 2026-09-06: this branch was 41 commits behind desk-sync-clean and the box was still
# running GATEWAY_FAMILY_POPULATIONS = ("hunt16",) -- 65 of 66 certificates unexecutable -- and a
# shadow_admission with no CANON_SOURCES, so nothing could enrol at all. Both had been fixed days
# earlier. The dashboard's CERTIFIED-NOT-ENROLLED rows and its dead certificates were not desk
# defects; they were a delivery defect wearing their clothes. Five merges landed tonight and none
# of them could reach the box on their own.
#
# The fetch+merge below is the SAME machinery the rejection path already used -- park the dirty
# files that block the merge, merge FETCH_HEAD, put them back byte-for-byte -- hoisted so it runs
# first. A conflict still aborts and leaves the work local for a human; nothing here guesses at a
# resolution on a tree that places trades.
$pushed = $false
for ($attempt = 1; $attempt -le 3 -and -not $pushed; $attempt++) {
    $pushRc = Git-In-Repo @("push", "origin", $branch)
    if ($pushRc -eq 0) { $pushed = $true; break }

    Write-SyncLog "push rejected (attempt $attempt), checking whether canonical adoption is required"
    $fetchRc = Git-In-Repo @("fetch", "origin", $branch)
    if ($fetchRc -ne 0) { Write-SyncLog "ABORT: git fetch failed rc=$fetchRc"; exit 1 }

    # FETCH_HEAD, not origin/$branch: a `git fetch origin <branch>` with an explicit branch
    # argument does NOT update the origin/<branch> remote-tracking ref unless one already exists
    # and is configured for it -- confirmed live on Contabo (2026-08-23), where `git log
    # origin/claude/...` failed with "unknown revision" right after a successful fetch of the
    # same branch. FETCH_HEAD is always populated by the fetch that just ran, regardless of
    # tracking-ref configuration, so it is the only reliable target here.
    # EVERY EXIT FROM THIS LOOP NOW SAYS SO. It used to leave through `exit 1` with no line
    # written, so the log's last word on a failed pass was "fetch+merge and retry" -- an
    # announcement of an intention, recorded as though it were an outcome. On the desk box that
    # exact line was the final entry of roughly 800 consecutive passes between 2026-08-26 and
    # 2026-09-06 while the box committed locally and published nothing. A silence that reads like
    # progress is worse than an error: it is the reason nobody looked for eleven days.
    $behind = @(& git -C $RepoRoot rev-list --count "HEAD..FETCH_HEAD") | Select-Object -First 1
    if ($behind -and [int]$behind -gt 0) {
        Request-Adoption -Branch $branch -Reason "push race left $behind inbound commit(s)"
        Write-SyncLog "local state commit is safe; publication resumes after canonical adoption"
        $ok = Publish-StateOnto -RepoRoot $RepoRoot -Branch $branch -Paths $existing
        if ($ok) { exit 0 } else { exit 1 }
    }
    Write-SyncLog "push failed without an inbound commit; retrying after a short backoff"
    Start-Sleep -Seconds 2
}

if (-not $pushed) {
    Write-SyncLog "ABORT: push still failing after 3 attempts"
    exit 1
}

Write-SyncLog ("shadow state synced to git: {0}" -f ($existing -join ", "))
exit 0
