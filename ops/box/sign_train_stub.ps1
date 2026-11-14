# THE SIGN TRAIN'S INSTALLED STUB (2026-11-11). Installed as bin\sign_train_leg.ps1.
#
# Desk health's read (sign_train_pr_head_read, fact 1): Quant-SignTrain ran an installed COPY of
# the leg, so every merged change to ops/box/sign_train_leg.ps1 did nothing until an
# administrator re-ran install_unattended.ps1. This stub is the one copy that is installed. Each
# run it brings the train's admin-only clone (C:\ProgramData\QuantBox\sign-repo) to a clean,
# detached origin/LIVE, exactly as the leg itself does, and runs the leg FROM THAT CHECKOUT. A
# change to the leg then takes effect on the first run after it merges, with no re-install.
#
# TRUSTED CODE ONLY, as in workflow_gate.ps1: the leg is read from origin/LIVE, never from a PR,
# in a folder the installer proved only Administrators and SYSTEM can write. The stub reads no
# token and takes no lock: the task runs one instance at a time (IgnoreNew), and the leg holds
# the train's mutex for everything after this point.

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    [string] $Python = "C:\Program Files\Python314\python.exe"
)
$ErrorActionPreference = 'Stop'
$LogDir = Join-Path $Root "logs"
$Clone = Join-Path $Root "sign-repo"
$log = Join-Path $LogDir "sign_train.log"
$beat = Join-Path $LogDir "sign_train.json"

function Say([string] $line) {
    Add-Content -LiteralPath $log -Value ("{0} stub: {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'), $line)
}
# A stub that cannot reach the leg still beats, so the merge-pipeline watcher goes RED on it.
function Fail([string] $note) {
    Say "FAILED: $note"
    $fails = 1
    try { $fails = [int]((Get-Content -LiteralPath $beat -Raw | ConvertFrom-Json).fail_runs) + 1 } catch { }
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); rc = 1; note = "stub: $note"; fail_runs = $fails; mutex_held_runs = 0 }
    [System.IO.File]::WriteAllText("$beat.tmp", ($doc | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath "$beat.tmp" -Destination $beat -Force
    exit 1
}

foreach ($v in @('GITHUB_TOKEN', 'GH_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN')) {
    Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue
}
$env:GIT_TERMINAL_PROMPT = '0'
$env:GIT_CONFIG_COUNT = '2'
$env:GIT_CONFIG_KEY_0 = 'safe.directory'
$env:GIT_CONFIG_VALUE_0 = ($Clone -replace '\\', '/')
$env:GIT_CONFIG_KEY_1 = 'core.autocrlf'
$env:GIT_CONFIG_VALUE_1 = 'false'

try {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $ErrorActionPreference = 'Continue'  # native stderr is data; exit codes are the verdict
    # Full history (the CLEAR record must be proven append-only), blobs fetched as needed.
    if (-not (Test-Path -LiteralPath (Join-Path $Clone ".git"))) {
        & git clone -q --filter=blob:none --no-checkout "https://github.com/$Repo.git" $Clone 2>&1 | ForEach-Object { Say "clone: $_" }
        if ($LASTEXITCODE -ne 0) { Fail "git clone failed ($LASTEXITCODE)" }
    }
    & git -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}" 2>&1 | ForEach-Object { Say "fetch: $_" }
    if ($LASTEXITCODE -ne 0) { Fail "git fetch failed ($LASTEXITCODE)" }
    & git -C $Clone checkout -q -f --detach "origin/$Live" 2>&1 | ForEach-Object { Say "checkout: $_" }
    if ($LASTEXITCODE -ne 0) { Fail "git checkout failed ($LASTEXITCODE)" }
    & git -C $Clone clean -q -fdx 2>&1 | ForEach-Object { Say "clean: $_" }
    $leg = Join-Path $Clone "ops\box\sign_train_leg.ps1"
    if (-not (Test-Path -LiteralPath $leg)) { Fail "no leg at $leg on LIVE" }
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $leg -Root $Root -Repo $Repo -Live $Live -Gh $Gh -Python $Python
    exit $LASTEXITCODE
} catch {
    Fail $_.Exception.Message
}
