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
    Write-Output $line
    try {
        New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
        Add-Content -Path $log -Value $line -Encoding utf8
    } catch {}
}

function Git-In-Repo {
    param([string[]] $GitArgs)
    & git -C $RepoRoot @GitArgs
    return $LASTEXITCODE
}

# Desk-relative paths of every state file this sync carries. Each MUST already be individually
# allowlisted in .gitignore (git add is silently a no-op on an ignored path otherwise, which
# would look like success while publishing nothing -- exactly the failure mode this script exists
# to avoid repeating).
$relPaths = @(
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/data/gateway_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/regime_state.json"
)
$existing = @()
foreach ($rel in $relPaths) {
    $full = Join-Path $RepoRoot ($rel -replace "/", "\")
    if (Test-Path $full) { $existing += $rel }
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
    Write-SyncLog "no change since last sync"
    exit 0
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd_HHmm")
$commitRc = Git-In-Repo @("commit", "-m", "mt5 shadow state sync $stamp")
if ($commitRc -ne 0) { Write-SyncLog "ABORT: git commit failed rc=$commitRc"; exit 1 }

$branch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD).Trim()
$pushed = $false
for ($attempt = 1; $attempt -le 3 -and -not $pushed; $attempt++) {
    $pushRc = Git-In-Repo @("push", "origin", $branch)
    if ($pushRc -eq 0) { $pushed = $true; break }

    Write-SyncLog "push rejected (attempt $attempt), fetch+merge and retry"
    $fetchRc = Git-In-Repo @("fetch", "origin", $branch)
    if ($fetchRc -ne 0) { Write-SyncLog "ABORT: git fetch failed rc=$fetchRc"; exit 1 }

    # FETCH_HEAD, not origin/$branch: a `git fetch origin <branch>` with an explicit branch
    # argument does NOT update the origin/<branch> remote-tracking ref unless one already exists
    # and is configured for it -- confirmed live on Contabo (2026-08-23), where `git log
    # origin/claude/...` failed with "unknown revision" right after a successful fetch of the
    # same branch. FETCH_HEAD is always populated by the fetch that just ran, regardless of
    # tracking-ref configuration, so it is the only reliable target here.
    $mergeRc = Git-In-Repo @("merge", "--no-edit", "FETCH_HEAD")
    if ($mergeRc -ne 0) {
        Write-SyncLog "ABORT: merge conflict against FETCH_HEAD (origin/$branch) -- aborting merge, leaving commit local for a human"
        Git-In-Repo @("merge", "--abort") | Out-Null
        exit 1
    }
    Start-Sleep -Seconds 2
}

if (-not $pushed) {
    Write-SyncLog "ABORT: push still failing after 3 attempts"
    exit 1
}

Write-SyncLog ("shadow state synced to git: {0}" -f ($existing -join ", "))
exit 0
