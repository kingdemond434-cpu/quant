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
    "desks/mt5/data/release_identity.json"
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
    # PARK THE FILES THAT BLOCK THE MERGE, MERGE, PUT THEM BACK.
    #
    # git refuses to merge when incoming commits touch a file with local modifications, and this
    # box rewrites hundreds of tracked artifacts continuously. Measured 2026-09-03: 376 files were
    # dirty and 60 were incoming, but the OVERLAP -- the only thing actually blocking the merge --
    # was TWO: desks/mt5/data/sync_marker.json and desks/mt5/data/universe/universe.json. Neither
    # is on this sync's allowlist, so it never commits them, so they are dirty forever and every
    # merge failed forever. `git merge-tree` reported the merge itself as CLEAN (rc 0); nothing
    # was in conflict but the working tree.
    #
    # The cost of that was not small: 616 commits sat unpushed on this box, unseen by every other
    # brain, while this file's own header calls itself the cross-brain visibility path.
    #
    # The local copies are COPIED ASIDE, not stashed (R0423 forbids `git stash` in a shared tree)
    # and not discarded -- universe.json is a protected registry whose records may not vanish.
    # After the merge they are restored byte-for-byte, so the working tree ends exactly as it
    # began and the only thing that changed is that the merge could run.
    $blockers = @()
    $incoming = @(& git -C $RepoRoot diff --name-only HEAD FETCH_HEAD) | Where-Object { $_ }
    foreach ($rel in $incoming) {
        $st = @(& git -C $RepoRoot status --porcelain -- $rel) | Where-Object { $_ }
        if ($st) { $blockers += $rel }
    }
    $parked = @{}
    foreach ($rel in $blockers) {
        $full = Join-Path $RepoRoot ($rel -replace "/", "\")
        if (Test-Path $full) {
            $tmp = [System.IO.Path]::GetTempFileName()
            Copy-Item -LiteralPath $full -Destination $tmp -Force
            $parked[$rel] = $tmp
            Git-In-Repo @("checkout", "--", $rel) | Out-Null
        }
    }
    if ($parked.Count) {
        Write-SyncLog ("parked {0} dirty file(s) that block the merge: {1}" -f `
                       $parked.Count, ($parked.Keys -join ", "))
    }

    $mergeRc = Git-In-Repo @("merge", "--no-edit", "FETCH_HEAD")

    foreach ($rel in $parked.Keys) {
        $full = Join-Path $RepoRoot ($rel -replace "/", "\")
        Copy-Item -LiteralPath $parked[$rel] -Destination $full -Force
        Remove-Item -LiteralPath $parked[$rel] -Force -ErrorAction SilentlyContinue
    }
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
