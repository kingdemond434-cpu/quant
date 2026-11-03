# THE RELEASE AUTHORITY'S 10-MINUTE PASS (scheduled task Quant-ReleaseAuthority, as quant-authority).
# Installed as a COPY outside the checkout (install_authority.ps1), so what runs here never comes
# from a PR. It moves its clean checkout to LIVE, refuses to go on when any ROOT file differs from
# the commit zuck pinned (C:\opt\audit_registry\ROOT_PIN.json), mints a read-only App token for
# this process only, and runs authority.py, which signs CLEAR/HOLD attestations into the folder
# the box gate reads. It never merges, pushes, comments or labels.
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $AppId,
    [Parameter(Mandatory)] [string] $InstallationId,
    [string] $Python = "C:\Program Files\Python314\python.exe",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Home_ = "C:\opt\authority",
    [string] $Registry = "C:\opt\audit_registry",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe"
)
$ErrorActionPreference = 'Stop'
$Clone = Join-Path $Home_ "repo"
$log = Join-Path $Home_ "authority.log"
function Say([string] $l) { Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format o), $l) }
foreach ($v in @('GITHUB_TOKEN', 'GH_TOKEN')) { Remove-Item -LiteralPath "env:$v" -ErrorAction SilentlyContinue }
try {
    if (Test-Path (Join-Path $Registry "attestations\DEACTIVATE")) { Say "DEACTIVATE present: nothing signed"; exit 0 }
    & git -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
    if ($LASTEXITCODE -ne 0) { throw "fetch failed" }
    & git -C $Clone checkout -q -f --detach "origin/$Live"
    & git -C $Clone clean -q -fdx
    $pin = Get-Content -Raw (Join-Path $Registry "ROOT_PIN.json") | ConvertFrom-Json
    $policy = (& git -C $Clone show "$($pin.commit):ops/release/authority/ROOT_POLICY.json" | Out-String) | ConvertFrom-Json
    $specs = @($policy.root_files | ForEach-Object { ":(glob)$_" })
    & git -C $Clone diff --quiet $pin.commit HEAD -- @specs
    if ($LASTEXITCODE -ne 0) { Say "ROOT files on LIVE differ from the pinned commit $($pin.commit): nothing signed"; exit 2 }
    $env:GH_TOKEN = (& $Python -I (Join-Path $Clone "ops\release\authority\mint_app_token.py") --app-id $AppId --installation-id $InstallationId --key (Join-Path $Home_ "key\app.pem")).Trim()
    $env:PATH = (Split-Path -Parent $Gh) + ';' + $env:PATH
    Push-Location -LiteralPath $Clone
    try {
        & $Python -I -u (Join-Path $Clone "ops\release\authority\authority.py") --repo $Repo --base $Live `
            --out (Join-Path $Registry "attestations") --key (Join-Path $Home_ "key\authority.pem") `
            --root-pin (Join-Path $Registry "ROOT_PIN.json") 2>&1 | ForEach-Object { Say "$_" }
        $rc = $LASTEXITCODE
    } finally { Pop-Location; Remove-Item env:GH_TOKEN -ErrorAction SilentlyContinue }
    Say "pass rc=$rc"
    exit $rc
} catch {
    Say "failed: $($_.Exception.Message)"
    exit 1
}
