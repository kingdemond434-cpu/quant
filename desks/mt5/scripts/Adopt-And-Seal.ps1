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
$py      = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

function Log([string] $m) { "$((Get-Date).ToUniversalTime().ToString('u')) adopt-and-seal: $m" }

# ---------------------------------------------------------------- 1. adopt the branch's tree
$adoptScript = Join-Path $desk "scripts\Adopt-Release.ps1"
if (-not (Test-Path $adoptScript)) { Log "Adopt-Release.ps1 missing at $adoptScript"; exit 2 }
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adoptScript `
    -RepoRoot $RepoRoot -Branch $Branch
$adoptExit = $LASTEXITCODE
if ($adoptExit -ne 0) {
    Log "Adopt-Release exited $adoptExit -- partial adoption; NOT sealing a tree that only half-matches the branch"
    exit $adoptExit
}

# ------------------------------------------------------ 2. seal, only if HEAD is not sealed
$head = (git rev-parse HEAD 2>$null | Out-String).Trim()
if (-not $head) { Log "cannot read HEAD"; exit 2 }
$sealed = ""
if (Test-Path $release) {
    try { $sealed = [string](Get-Content $release -Raw | ConvertFrom-Json).code_sha } catch { $sealed = "" }
}
if ($sealed -eq $head) {
    Log "HEAD $($head.Substring(0,12)) is already the sealed code; nothing to do"
    exit 0
}
# `release.seal` refuses a dirty tree. Say so HERE, with the paths, rather than let a Python
# traceback be the only record. Untracked files (??) are not dirt; tracked modifications are.
$dirty = @(git status --porcelain 2>$null | Where-Object { $_ -and ($_ -notmatch '^\?\?') })
if ($dirty.Count -gt 0) {
    Log "refusing to seal: $($dirty.Count) tracked path(s) differ from HEAD after adoption:"
    $dirty | Select-Object -First 12 | ForEach-Object { Log "    $_" }
    exit 3
}
& $py -c "from libs.ops import release; d=release.seal(by='Adopt-And-Seal'); print(d.get('code_sha') or d.get('live_sha'))"
if ($LASTEXITCODE -ne 0) { Log "release.seal failed (exit $LASTEXITCODE)"; exit 4 }

# --------------------------------------------- 3. RELEASE.json alone -- the pure-seal commit
git add -- "desks/mt5/data/RELEASE.json"
git commit -q -m "Seal release $($head.Substring(0,12)) (Adopt-And-Seal, unattended)"
if ($LASTEXITCODE -ne 0) { Log "seal commit failed (exit $LASTEXITCODE)"; exit 5 }

# ---------------------------------------- 4. the gateway reads the seal at start; restart it
Stop-ScheduledTask  -TaskName "MT5-Gateway" -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName "MT5-Gateway" -ErrorAction SilentlyContinue
Log "sealed $($head.Substring(0,12)) from $Branch and restarted MT5-Gateway"
exit 0
