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
    "desks/mt5/reports/attribution_chain.json",
    # THE MARKOUT ITSELF (2026-09-30). The daily markout leg writes markout.json beside
    # attribution_chain.json, but only the chain crossed the wire, so the VPS's desk state read
    # `execution.matched_fills` off the 2026-09-08 stub committed before the ledger carried any
    # entry-order key -- "matched_fills 0" for three weeks while the join on the box had moved.
    "desks/mt5/reports/markout.json",
    # THE TIER S BOX ATTESTATION (2026-09-30). Every tier_s pass writes it: per layer, whether
    # its artifact is fresh on THIS host and its contract not REJECTED, plus digests of TIER_S,
    # ALPHA_RANK, ONLINE_FDR_ROWS, IMMUNE, allocator_tilts, research_budget, the door verdicts
    # and CONTRACTS (all gitignored or box-local where written). A Tier S layer is DONE only on
    # this file as committed from the trading box (scripts/check_tier_s_program.py).
    "desks/mt5/data/tier_s/box_evidence.json",
    "desks/mt5/data/tier_s/live_door.json",
    # THE TIER S MEASUREMENT REPORTS (2026-09-30). The independent audit found no committed
    # artifact for the null lab, the lag lane or the occupancy map: `**/reports/*` is ignored, so
    # every one of them existed only on the host that wrote it. NULL_LAB (hourly leg null_lab),
    # KNOWN_BY_DATE + PIT_LAG_CENSUS (leg pit_canaries), OCCUPANCY_MAP + CULTURE_ORTHOGONALITY
    # (leg occupancy_map), RESEARCH_LIVE_IDENTITY (leg research_live_identity). Outputs of the
    # running code, each negated in .gitignore and declared NON_CODE in both seal lists.
    "desks/mt5/reports/NULL_LAB.json",
    "desks/mt5/reports/KNOWN_BY_DATE.json",
    "desks/mt5/reports/PIT_LAG_CENSUS.json",
    # UNKNOWN_SHARE_CENSUS (daily step unknown_census): the judged-denominator UNKNOWN share
    "desks/mt5/reports/UNKNOWN_SHARE_CENSUS.json",
    "desks/mt5/reports/OCCUPANCY_MAP.json",
    "desks/mt5/reports/CULTURE_ORTHOGONALITY.json",
    "desks/mt5/reports/RESEARCH_LIVE_IDENTITY.json",
    # THE REST OF THE TIER S PROMOTION DOOR'S EVIDENCE (2026-09-30). `promotion_authority` reads
    # six box-local files to decide whether a candidate may go LIVE: live_door (above), the door
    # verdicts, the immune system's PROMOTION_FREEZE, the regression stop's RELEASE_STOP, the
    # online-FDR rows and the replication verdicts. Only live_door and the attestation crossed
    # the wire, so no reader off the box could say WHY a promotion was withheld. Small JSON, each
    # declared NON_CODE in both seal lists and (for the two under reports/) negated in
    # .gitignore; tests/ops/test_tier_s_evidence_publication.py pins all four properties.
    "desks/mt5/data/tier_s/door_verdicts.json",
    "desks/mt5/data/tier_s/PROMOTION_FREEZE.json",
    "desks/mt5/data/tier_s/RELEASE_STOP.json",
    "desks/mt5/reports/tier_s/ONLINE_FDR_ROWS.json",
    "desks/mt5/reports/REPLICATION.json"
)
$existing = @()
foreach ($rel in $relPaths) {
    $full = Join-Path $RepoRoot ($rel -replace "/", "\")
    if (Test-Path $full) { $existing += $rel }
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
if ($script:InboundAdoptionRequired) {
    # Exit success: this pass completed its responsibility by handing inbound code to the one
    # task allowed to adopt and seal it. The next scheduled publisher pass will publish runtime
    # state after adoption converges.
    exit 0
}

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
        exit 0
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
