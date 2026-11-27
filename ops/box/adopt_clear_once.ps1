<#
.SYNOPSIS
    THE ONE BOOTSTRAP ONTO THE AUDIT-CLEAR RELEASE AUTHORITY (zuck 2026-11-25 18:53Z). Input: the
    exact 40-hex LIVE head to adopt. Logs to C:\ProgramData\QuantBox\logs\adopt_clear_once_<UTC>.log.

.DESCRIPTION
    WHY. The running adopter (MT5-AdoptRelease, from the box's own tree) still asks the CI
    `production` pointer, which no longer moves, so it holds forever and can never adopt the
    adopter that drops that rule. adopt_once.ps1 needs a release/* tag and production, which the
    new authority does not make. This is the same single step with the new rule: run the TARGET's
    own Adopt-And-Seal against the box with -GuardRoot, every guard step on.

    WHAT IT DOES, IN ORDER (any failure stops before the next):
      1. Refuses unless elevated.
      2. Takes -Sha and checks its shape (40 hex).
      3. Clones C:\opt\quant's own `origin` (the forge; no GitHub) into
         C:\ProgramData\QuantBox\adopt-clear-once\<sha12>, never into C:\opt\quant, and fetches LIVE.
      4. Verifies: the sha is on origin/LIVE, carries the guard fix (#1216), and its
         Adopt-And-Seal.ps1 takes -GuardRoot and knows ADOPT_CLEAR.
      5. Runs THAT Adopt-And-Seal.ps1 -RepoRoot C:\opt\quant -GuardRoot <checkout>. Its release gate
         (authority audit_clear), adopt_guard pre (an auditor CLEAR row for every governed path),
         blackout, smoke, seal, health and automatic rollback all run exactly as the hourly task.
      6. Prints the adopter's exit code and the stage it reached (ADOPTION_HEARTBEAT.json).

    WHAT IT NEVER DOES. No flag that skips a check, no -AllowUnreleased, no write into
    C:\opt\quant except through Adopt-And-Seal.ps1, no credential, no task created or changed.

    powershell -NoProfile -ExecutionPolicy Bypass -File ops\box\adopt_clear_once.ps1 -Sha <40 hex>
#>
param(
    [string] $Sha,
    [string] $QuantRoot = "C:\opt\quant",
    [string] $Root = "C:\ProgramData\QuantBox"
)

$ErrorActionPreference = "Continue"
$Live = "claude/llm-auto-upgrade-verify-gcjac3"
$GuardFix = "ccc2fbb396db3a677906586d8a4c0f5c29ab2cc2"

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$logDir = Join-Path $Root "logs"
$null = New-Item -ItemType Directory -Force -Path $logDir -ErrorAction SilentlyContinue
$log = Join-Path $logDir "adopt_clear_once_$stamp.log"
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

Say "adopt_clear_once: user $env:USERNAME on $env:COMPUTERNAME"

# 1. ELEVATED, because the adopter writes C:\opt\quant and restarts tasks.
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Finish 2 "NOT STARTED: this window is not elevated."
}

# 2. THE EXACT HEAD, the only input.
$Sha = "$Sha".Trim().Trim('"').ToLowerInvariant()
if ($Sha -notmatch '^[0-9a-f]{40}$') { Finish 2 "NOT STARTED: '$Sha' is not a 40-hex commit." }
if ($env:QUANT_ADOPT_AUTHORITY -eq "release") { Finish 2 "NOT STARTED: QUANT_ADOPT_AUTHORITY=release is set; use adopt_once.ps1." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Finish 2 "NOT STARTED: git is not on PATH." }
if (-not (Test-Path -LiteralPath (Join-Path $QuantRoot ".git"))) { Finish 2 "NOT STARTED: $QuantRoot is not a git repository." }

$stage = Join-Path (Join-Path $Root "adopt-clear-once") $Sha.Substring(0, 12)
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '2'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($stage -replace '\\', '/')
$env:GIT_CONFIG_KEY_1 = 'safe.directory'
$env:GIT_CONFIG_VALUE_1 = ($QuantRoot -replace '\\', '/')

# 3. A FRESH CHECKOUT, from the live tree's own origin, in its own folder.
$origin = (& git -C $QuantRoot remote get-url origin 2>$null | Out-String).Trim()
if (-not $origin) { Finish 3 "NOT STARTED: $QuantRoot has no origin remote." }
if (Test-Path -LiteralPath $stage) {
    Say "removing the previous checkout at $stage"
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $stage) { Finish 3 "NOT STARTED: could not clear $stage." }
}
$null = New-Item -ItemType Directory -Force -Path (Split-Path $stage)
Say "cloning the live tree's origin into $stage"
if ((Git @("clone", "-q", "--no-checkout", $origin, $stage)) -ne 0) {
    Finish 3 "NOT STARTED: the clone failed. Nothing on the box changed."
}
if ((Git @("-C", $stage, "fetch", "-q", "--no-tags", "origin", "+refs/heads/${Live}:refs/remotes/origin/${Live}")) -ne 0) {
    Finish 3 "NOT STARTED: could not fetch the live branch. Nothing on the box changed."
}

# 4. THE HEAD, VERIFIED.
& git -C $stage cat-file -e "$Sha^{commit}" 2>$null
if ($LASTEXITCODE -ne 0) { Finish 4 "NOT STARTED: $Sha is not in origin." }
& git -C $stage merge-base --is-ancestor $Sha "refs/remotes/origin/$Live" 2>$null
if ($LASTEXITCODE -ne 0) { Finish 4 "NOT STARTED: $($Sha.Substring(0, 12)) is not on the live branch." }
& git -C $stage merge-base --is-ancestor $GuardFix $Sha 2>$null
if ($LASTEXITCODE -ne 0) { Finish 4 "NOT STARTED: this head does not carry the guard fix (#1216)." }
if ((Git @("-C", $stage, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", $Sha)) -ne 0) {
    Finish 3 "NOT STARTED: checkout of $($Sha.Substring(0, 12)) failed."
}
$adopter = Join-Path $stage "desks\mt5\scripts\Adopt-And-Seal.ps1"
if (-not (Test-Path -LiteralPath $adopter) -or
    -not (Select-String -LiteralPath $adopter -SimpleMatch '[string] $GuardRoot' -Quiet) -or
    -not (Select-String -LiteralPath $adopter -SimpleMatch '"ADOPT_CLEAR"' -Quiet)) {
    Finish 4 "NOT STARTED: this head's Adopt-And-Seal.ps1 lacks -GuardRoot or ADOPT_CLEAR."
}
Say "verified: on the live branch, carries #1216, adopter takes -GuardRoot and ADOPT_CLEAR"

$task = Get-ScheduledTask -TaskName "MT5-AdoptRelease" -ErrorAction SilentlyContinue
if ($task) { Say ("MT5-AdoptRelease is {0}; the adopter waits for the git-writer lock if it is running" -f $task.State) }

# 5. THE TARGET'S OWN ADOPTER, WITH ITS OWN GUARD, EVERY CHECK ON.
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
    Finish 0 "DONE: the box adopted $($Sha.Substring(0, 12)) (stage $stageName). The hourly task takes it from here."
}
if ($rc -eq 0) { Finish 0 "NOT ADOPTED YET: the adopter held (stage $stageName), with every check on. Nothing was forced." }
Finish $rc "NOT ADOPTED: the adopter stopped at stage '$stageName' (exit $rc) and kept or restored the running release."
