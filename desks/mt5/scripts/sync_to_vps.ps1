# sync_to_vps.ps1 - hourly push of the MT5 desk's ARTIFACTS to the VPS brains.
# Runs from MT5Sync.cmd every 60s; executes the actual sync at most hourly
# (marker: data/sync_marker.json last_cycle; state: data/last_sync.json).
#
# ============================================================================
# THIS SCRIPT USED TO SYNC CODE, AND THAT IS WHERE THE REVERTS CAME FROM
# ============================================================================
#
# It copied mt5desk\, research\, docs\ and scripts\ out of C:\Users\dell\mt5-research --
# which is NOT a git checkout -- scp'd them over /home/quant/quant-platform/desks/mt5/, then ran
#
#     git add desks/mt5 && git commit -m 'mt5 desk hourly sync ...' && git push
#
# with no fetch, no pull, no merge and no rebase anywhere in the chain. Every git-tracked file
# that existed on both sides was overwritten by this box's copy and committed as the new truth,
# once an hour, forever. It could not merge; there was nothing in it that could.
#
# THE COST, three times over: 79ab4705 reverted nine closed defects in one commit -- gold priced
# at 3% of its spread in engine.py, the account filter in promoter.py, the risk-budget import in
# allocation.py, the date-index join in qquant_gates.py, the promotion chain's own scheduler in
# hourly_cycle.py -- and deleted Costs.from_symbol while SEVENTEEN files still called it. The
# lookahead fix in run_hunt12.py has now been restored three separate times (87689ac3, f7cef38f,
# 06518c4a) because this loop keeps putting it back.
#
# It also silenced itself: every scp and ssh result went to Out-Null, and `git push -q` with no
# pull fails on a non-fast-forward. So divergence accumulated with no error anywhere, and the
# only symptom was fixed code quietly becoming unfixed.
#
# THE FIX IS NOT A BETTER MERGE. IT IS THAT CODE MUST NOT TRAVEL BY scp.
#
# The VPS at /home/quant/quant-platform IS a git checkout. It already has every code file, from
# git, with history. Copying a second, historyless version on top of that can only ever destroy
# information -- there is no state of the world in which the scp'd copy is better than what git
# holds, because anything genuinely newer on this box belongs in a commit.
#
# So the bundle now carries ARTIFACTS ONLY: data\ and reports\, the things git does not track
# and the VPS cannot obtain any other way. Code reaches the VPS by `git pull`, which this script
# now runs before committing.
#
# IF THIS BOX HAS LOCAL CODE EDITS, THEY ARE NOT STRANDED -- THEY ARE UNCOMMITTED. Commit them
# from the quant-platform checkout like every other brain does. That is not extra ceremony; it
# is the one door in docs/UNIVERSAL_PROMOTION_PROTOCOL.md, and a working directory that
# overwrites the repo hourly is the definition of a private one.
#
# To restore the old behaviour set SYNC_CODE below to $true. Doing so re-arms the revert loop,
# so it is a decision to make deliberately and not a default to drift back into.

$ErrorActionPreference = "Continue"
$base = "C:\Users\dell\mt5-research"
$marker = Join-Path $base "data\sync_marker.json"
$last   = Join-Path $base "data\last_sync.json"
$log    = Join-Path $base "logs\sync_to_vps.log"
$bundle = Join-Path $env:TEMP "opencode\mt5_desk_bundle"
$vpsHost = "quant@95.216.191.70"
$vpsRepo = "/home/quant/quant-platform"
$vps = "${vpsHost}:${vpsRepo}/desks/mt5/"
$branch = "claude/llm-auto-upgrade-verify-gcjac3"

# Set to $true ONLY to deliberately re-arm code-over-git syncing. See the header.
$SYNC_CODE = $false

function Write-SyncLog($msg) {
    $line = "{0} {1}" -f (Get-Date -Format "o"), $msg
    Write-Output $line
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
        Add-Content -Path $log -Value $line -Encoding utf8
    } catch {}
}

$now = Get-Date
$lastSync = $null
if (Test-Path $last) {
    try { $lastSync = (Get-Content $last -Raw | ConvertFrom-Json).last_sync } catch {}
}
$due = $true
if ($lastSync) {
    try {
        $t = [datetime]::Parse($lastSync)
        $due = ($now - $t).TotalMinutes -ge 60
    } catch { $due = $true }
}
if (-not $due) { exit 0 }

# 1. Build the bundle. ARTIFACTS ONLY unless code sync is explicitly re-armed.
if (Test-Path $bundle) { Remove-Item -Recurse -Force $bundle }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

if ($SYNC_CODE) {
    Write-SyncLog "WARNING: SYNC_CODE is on -- this scp can revert git-tracked fixes. See header."
    foreach ($d in @("mt5desk", "research", "docs", "scripts")) {
        $src = Join-Path $base $d
        if (Test-Path $src) { Copy-Item -Path $src -Destination $bundle -Recurse -Force }
    }
    foreach ($f in @("AGENTS.md", "CLAUDE.md")) {
        $p = Join-Path $base $f
        if (Test-Path $p) { Copy-Item $p -Destination $bundle -Force }
    }
}

# reports\ is an artifact directory: the gates, ledgers and survivor files the VPS produces no
# other way. It stays in the bundle whether or not code does.
$srcReports = Join-Path $base "reports"
if (Test-Path $srcReports) { Copy-Item -Path $srcReports -Destination $bundle -Recurse -Force }

$dataOut = Join-Path $bundle "data"
New-Item -ItemType Directory -Force -Path $dataOut | Out-Null
$src = Join-Path $base "data"
foreach ($d in @("universe", "states", "cot", "cot_tff", "cot_disagg", "lake",
                 "gateway_state.json","live_ledger.jsonl","regime_state.json",
                 "sleeves.json","terminal_path.txt","GATEWAY_PAUSED",
                 "frontier_inbox.json","sync_marker.json","data_registry.json",
                 "free_data_frontier.json","cot_tff.json","research_queue.json",
                 "macro_state.json","cross_asset_anchors.pkl","crowding_state.json",
                 "options_archive.parquet","news_state.json","HOLD_qquant_gates",
                 "HOLD_universal","HOLD_merge","HOLD_allocation","HOLD_qquant")) {
    $p = Join-Path $src $d
    if (Test-Path $p) { Copy-Item $p -Destination $dataOut -Recurse -Force }
}

# 2. PULL BEFORE ANYTHING LANDS. The VPS must be current before this box's artifacts are written
#    over it, so that a commit made here is a commit on top of the shared history rather than
#    beside it. `git push -q` on a stale checkout fails as a non-fast-forward, which is precisely
#    the failure the old script routed to Out-Null.
$ssh = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $ssh) { Write-SyncLog "ABORT: ssh not on PATH"; exit 1 }

$pullCmd = "cd $vpsRepo && git fetch origin $branch && git merge --no-edit origin/$branch"
$pullOut = & $ssh -o ConnectTimeout=20 $vpsHost $pullCmd 2>&1
if ($LASTEXITCODE -ne 0) {
    # FAIL CLOSED. Committing artifacts on top of a checkout that could not take the shared
    # history is how two trees drift apart, and drifting apart silently is the whole defect.
    Write-SyncLog "ABORT: VPS could not merge origin/$branch -- $($pullOut -join ' | ')"
    exit 1
}
Write-SyncLog "pulled: $($pullOut | Select-Object -Last 1)"

# 3. Upload
$scp = Get-Command scp -ErrorAction SilentlyContinue
if (-not $scp) { Write-SyncLog "ABORT: scp not on PATH"; exit 1 }
$scpOut = & $scp -r -q "$bundle\*" $vps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-SyncLog "ABORT: scp failed -- $($scpOut -join ' | ')"
    exit 1
}

# 4. Commit + push on the VPS repo (whole-brain visibility).
#    `git add` is scoped to the artifact paths when code sync is off, so a stray edit in the
#    VPS's own working tree cannot ride along inside an "hourly sync" commit unnoticed.
$addPaths = if ($SYNC_CODE) { "desks/mt5" } else { "desks/mt5/data desks/mt5/reports" }
$stamp = Get-Date -Format yyyy-MM-dd_HHmm
$pushCmd = "cd $vpsRepo && git add $addPaths && " +
           "(git diff --cached --quiet && echo 'sync: nothing to commit' || " +
           "(git commit -m 'mt5 desk hourly artifact sync $stamp' -q && git push origin $branch))"
$pushOut = & $ssh -o ConnectTimeout=40 $vpsHost $pushCmd 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-SyncLog "FAILED: commit/push -- $($pushOut -join ' | ')"
    exit 1
}
Write-SyncLog "synced ok: $($pushOut | Select-Object -Last 1)"

# 5. Record. Only after a run that actually succeeded -- stamping the marker on a failed sync
#    buys an hour of silence before the next attempt, which is an hour of believing a broken
#    sync is a working one.
@{ last_sync = $now.ToString("o") } | ConvertTo-Json | Set-Content $last -Encoding utf8
exit 0
