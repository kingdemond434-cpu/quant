<#
.SYNOPSIS
    ONE RUN OF THE BOX'S OWN ADOPTER, DECIDED BY THE RELEASE'S OWN GUARD. The release tag is the
    only input. Everything is logged to C:\ProgramData\QuantBox\logs\adopt_once_<UTC stamp>.log.

.DESCRIPTION
    WHY THIS EXISTS (2026-11-17). The box adopts with the guard in its RUNNING tree. On 11-14 an
    ADOPT_CLEARS row landed spread over 33 lines; the running guard's parse_clears reads one row
    per line and refuses the whole file, and the file is append-only, so every later release is
    refused (MT5-AdoptRelease exit 8). #1216 reads such rows, but it can only reach the box
    through the adoption the old guard refuses. The scheduled task cannot get out of that loop by
    itself; this file is the one manual step that does, with nothing switched off.

    WHAT IT DOES, IN ORDER (each step logged, any failure stops before the next):
      1. Refuses unless the window is elevated (the adopter writes C:\opt\quant).
      2. Takes the tag (argument, or pasted at the prompt) and checks its shape:
         release/<yyyymmddThhmmssZ>-<12 hex>.
      3. Clones the public repository into C:\ProgramData\QuantBox\adopt-once\<tag> (its own
         folder, never C:\opt\quant) and fetches the tag and the live branch.
      4. Verifies the tag's commit: starts with the tag's 12 hex, is on the live branch, carries
         the guard fix (#1216, ccc2fbb39), and its Adopt-And-Seal.ps1 takes -GuardRoot.
      5. Checks out that commit and runs ITS Adopt-And-Seal.ps1 -RepoRoot C:\opt\quant
         -GuardRoot <that checkout>. The release gate and every guard step (heal, state-verify,
         pre, hold, smoke, blackout, health, rollback) run exactly as the hourly task runs them,
         from the release's code, against the box. The adopter refuses if the checkout has any
         local change or its commit is not an ancestor of the target the gate picks.
      6. Prints the adopter's exit code and the stage it reached (ADOPTION_HEARTBEAT.json).

    WHAT IT NEVER DOES. No flag that skips a check, no -AllowUnreleased, no write into
    C:\opt\quant except through Adopt-And-Seal.ps1 itself, no credentials (the repository is
    public), no scheduled task created or changed. After one successful run the hourly
    MT5-AdoptRelease task runs the fixed guard from the adopted tree and this file is not needed.

    powershell -NoProfile -ExecutionPolicy Bypass -File ops\box\adopt_once.ps1 -Tag release/...
#>
param(
    [string] $Tag,
    [string] $QuantRoot = "C:\opt\quant",
    [string] $Root = "C:\ProgramData\QuantBox"
)

$ErrorActionPreference = "Continue"
$Repo = "kingdemond434-cpu/quant"
$Live = "claude/llm-auto-upgrade-verify-gcjac3"
# #1216's merge: the guard that reads a row spread over lines. A release without it would be
# refused by the same guard again, so it is refused here first, with a plain reason.
$GuardFix = "ccc2fbb396db3a677906586d8a4c0f5c29ab2cc2"
$TagShape = '^release/\d{8}T\d{6}Z-([0-9a-f]{12})$'

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$logDir = Join-Path $Root "logs"
$null = New-Item -ItemType Directory -Force -Path $logDir -ErrorAction SilentlyContinue
$log = Join-Path $logDir "adopt_once_$stamp.log"
try { Start-Transcript -LiteralPath $log -Append | Out-Null } catch { }

function Say([string] $m) { Write-Host ("{0}  {1}" -f (Get-Date).ToUniversalTime().ToString("HH:mm:ss"), $m) }
function Finish([int] $code, [string] $plain) {
    Say $plain
    Say "log: $log"
    try { Stop-Transcript | Out-Null } catch { }
    exit $code
}
function Git([string[]] $a) {
    $out = @(& git @a 2>&1 | ForEach-Object { "$_" })
    $out | ForEach-Object { Say "  git: $_" }
    return $LASTEXITCODE
}

Say "adopt_once: user $env:USERNAME on $env:COMPUTERNAME"

# 1. ELEVATED, because the adopter writes C:\opt\quant and restarts tasks.
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Finish 2 "NOT STARTED: this window is not elevated. Right-click adopt_once.cmd and choose Run as administrator."
}

# 2. THE TAG, the only input.
if (-not $Tag) { $Tag = Read-Host "Paste the release tag (release/...)" }
$Tag = "$Tag".Trim().Trim('"')
if ($Tag -notmatch $TagShape) { Finish 2 "NOT STARTED: '$Tag' is not a release tag (release/<yyyymmddThhmmssZ>-<12 hex>)." }
$short = $Matches[1]
Say "tag: $Tag"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Finish 2 "NOT STARTED: git is not on PATH." }
if (-not (Test-Path -LiteralPath (Join-Path $QuantRoot ".git"))) { Finish 2 "NOT STARTED: $QuantRoot is not a git repository." }

# git trusts the two repositories this run touches through command-scope config only (an elevated
# admin and the SYSTEM-owned live tree differ in owner, which git calls "dubious ownership").
$stage = Join-Path (Join-Path $Root "adopt-once") ($Tag -replace '[/\\:]', '_')
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '2'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($stage -replace '\\', '/')
$env:GIT_CONFIG_KEY_1 = 'safe.directory'
$env:GIT_CONFIG_VALUE_1 = ($QuantRoot -replace '\\', '/')

# 3. A FRESH CHECKOUT OF THE RELEASE in its own folder.
if (Test-Path -LiteralPath $stage) {
    Say "removing the previous checkout at $stage"
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $stage) { Finish 3 "NOT STARTED: could not clear $stage." }
}
$null = New-Item -ItemType Directory -Force -Path (Split-Path $stage)
Say "cloning https://github.com/$Repo into $stage"
if ((Git @("clone", "-q", "--filter=blob:none", "--no-checkout", "https://github.com/$Repo.git", $stage)) -ne 0) {
    Finish 3 "NOT STARTED: the clone failed (network?). Nothing on the box changed."
}
$fetch = @("-C", $stage, "fetch", "-q", "--no-tags", "origin",
           "+refs/heads/${Live}:refs/remotes/origin/${Live}", "+refs/tags/${Tag}:refs/tags/${Tag}")
if ((Git $fetch) -ne 0) { Finish 3 "NOT STARTED: could not fetch $Tag or the live branch. Nothing on the box changed." }

# 4. THE TAG'S COMMIT, VERIFIED.
$sha = (& git -C $stage rev-parse "refs/tags/$Tag^{commit}" 2>$null | Out-String).Trim()
if ($sha -notmatch '^[0-9a-f]{40}$') { Finish 4 "NOT STARTED: $Tag does not name a commit." }
Say "commit: $sha"
if (-not $sha.StartsWith($short)) { Finish 4 "NOT STARTED: $Tag names $($sha.Substring(0, 12)), not $short." }
& git -C $stage merge-base --is-ancestor $sha "refs/remotes/origin/$Live" 2>$null
if ($LASTEXITCODE -ne 0) { Finish 4 "NOT STARTED: $($sha.Substring(0, 12)) is not on the live branch." }
& git -C $stage merge-base --is-ancestor $GuardFix $sha 2>$null
if ($LASTEXITCODE -ne 0) { Finish 4 "NOT STARTED: this release does not carry the guard fix (#1216); use a newer release." }
if ((Git @("-C", $stage, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", $sha)) -ne 0) {
    Finish 3 "NOT STARTED: checkout of $($sha.Substring(0, 12)) failed."
}
$adopter = Join-Path $stage "desks\mt5\scripts\Adopt-And-Seal.ps1"
if (-not (Test-Path -LiteralPath $adopter) -or -not (Select-String -LiteralPath $adopter -SimpleMatch '[string] $GuardRoot' -Quiet)) {
    Finish 4 "NOT STARTED: this release's Adopt-And-Seal.ps1 has no -GuardRoot; use a newer release."
}
Say "verified: on the live branch, carries #1216, adopter takes -GuardRoot"

$task = Get-ScheduledTask -TaskName "MT5-AdoptRelease" -ErrorAction SilentlyContinue
if ($task) { Say ("MT5-AdoptRelease is {0}; the adopter waits for the git-writer lock if it is running" -f $task.State) }

# 5. THE BOX'S OWN ADOPTER, FROM THE RELEASE, WITH THE RELEASE'S GUARD.
Say "running $adopter -RepoRoot $QuantRoot -GuardRoot $stage"
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $adopter -RepoRoot $QuantRoot -GuardRoot $stage 2>&1 |
    ForEach-Object { Say "  adopter: $_" }
$rc = $LASTEXITCODE

# 6. WHAT HAPPENED, in one line.
$stageName = ""
try {
    $hb = Get-Content -LiteralPath (Join-Path $QuantRoot "desks\mt5\reports\ADOPTION_HEARTBEAT.json") -Raw | ConvertFrom-Json
    $stageName = [string]$hb.stage
    Say ("heartbeat: stage {0}, exit {1}, head {2}" -f $hb.stage, $hb.exit_code, $hb.head_after)
} catch { Say "heartbeat unreadable" }
if ($rc -eq 0 -and $stageName -in @("sealed", "already-sealed", "target-unsealed", "accepts-nothing-to-seal")) {
    Finish 0 "DONE: the box adopted the release (stage $stageName). The hourly task takes it from here."
}
if ($rc -eq 0) { Finish 0 "NOT ADOPTED YET: the adopter held (stage $stageName), with every check on. Nothing was forced." }
Finish $rc "NOT ADOPTED: the adopter stopped at stage '$stageName' (exit $rc) and kept or restored the running release."
