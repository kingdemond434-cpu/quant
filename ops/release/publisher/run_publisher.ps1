# THE STATE PUBLISHER'S 5-MINUTE PASS (scheduled task Quant-StatePublisher, as quant-publisher).
# Installed as a COPY outside the checkout (install_publisher.ps1). It moves its clean clone to
# LIVE, refuses when any ROOT file differs from the commit zuck pinned (the publisher is root, so a
# PR can't change what it pushes without the owner's path and a re-pin), mints the state App's
# token for this process only, and runs publish.py, which pushes the box's STATE paths and nothing
# else (ops/release/authority/LEVEL2.md step 2). The token reaches git through GIT_CONFIG_* env
# entries, never argv or a file.
[CmdletBinding()]
param(
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Home_ = "C:\opt\publisher",
    [string] $Src = "C:\opt\quant",
    [string] $Registry = "C:\opt\audit_registry"
)
$ErrorActionPreference = 'Stop'
$Clone = Join-Path $Home_ "repo"
$cfg = Get-Content -Raw (Join-Path $Home_ "config.json") | ConvertFrom-Json
$log = Join-Path $Home_ "publisher.log"
function Say([string] $l) { Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format o), $l) }
foreach ($v in @('GITHUB_TOKEN', 'GH_TOKEN')) { Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue }
try {
    if (Test-Path (Join-Path $Home_ "DEACTIVATE")) { Say "DEACTIVATE present: nothing published"; exit 0 }
    & git -c safe.directory=* -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
    if ($LASTEXITCODE -ne 0) { throw "fetch failed" }
    & git -c safe.directory=* -C $Clone checkout -q -f --detach "origin/$Live"
    $pin = Get-Content -Raw (Join-Path $Registry "ROOT_PIN.json") | ConvertFrom-Json
    $policy = (& git -c safe.directory=* -C $Clone show "$($pin.commit):ops/release/authority/ROOT_POLICY.json" | Out-String) | ConvertFrom-Json
    $specs = @($policy.root_files | ForEach-Object { ":(glob)$_" })
    & git -c safe.directory=* -C $Clone diff --quiet $pin.commit HEAD -- @specs
    if ($LASTEXITCODE -ne 0) { Say "ROOT files on LIVE differ from the pinned commit: nothing published"; exit 2 }
    $script = Join-Path $Home_ "publish.py"
    Copy-Item -Force (Join-Path $Clone "ops\release\publisher\publish.py") $script
    $tok = (& $cfg.python -I (Join-Path $Clone "ops\release\authority\mint_app_token.py") --app-id $cfg.app_id --installation-id $cfg.installation_id --key (Join-Path $Home_ "key\app.pem")).Trim()
    $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$tok"))
    $env:GIT_CONFIG_COUNT = "1"
    $env:GIT_CONFIG_KEY_0 = "http.https://github.com/.extraheader"
    $env:GIT_CONFIG_VALUE_0 = "AUTHORIZATION: basic $basic"
    try {
        & $cfg.python -I -u $script --src $Src --work $Clone --branch $Live 2>&1 | ForEach-Object { Say "$_" }
        $rc = $LASTEXITCODE
    } finally {
        foreach ($v in @('GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0')) { Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue }
        $tok = $null; $basic = $null
    }
    Say "pass rc=$rc"
    exit $rc
} catch {
    Say "failed: $($_.Exception.Message)"
    exit 1
}
