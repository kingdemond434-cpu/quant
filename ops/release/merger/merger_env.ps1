# LEVEL 2 STEP 3 (ops/release/authority/LEVEL2.md): THE BOX'S PR-SIDE GITHUB IDENTITY.
#
# Dot-sourced by ops/box/workflow_gate.ps1 and ops/box/sign_train_leg.ps1 from their own clean
# checkout of LIVE. With C:\opt\merger\config.json present (install_merger.ps1), it mints a
# "quant-merger" App token for THIS process only. The token reaches gh as GH_TOKEN and reaches git
# as a github.com-scoped extraheader appended to the caller's GIT_CONFIG_* entries; it never
# touches argv or disk. Without the config it does nothing, and zuck's gh login stays in use
# (Level 1).
#
# The key needs no account confinement. The App can merge PRs and push branches, but the LIVE
# ruleset refuses any LIVE change the release authority did not pass, whoever holds the key.
# Returns $true when the App identity is in use.
function Use-MergerIdentity([string] $CloneRoot) {
    $home_ = "C:\opt\merger"
    $cfgPath = Join-Path $home_ "config.json"
    if (-not (Test-Path -LiteralPath $cfgPath)) { return $false }
    $cfg = Get-Content -Raw -LiteralPath $cfgPath | ConvertFrom-Json
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $tok = (& $cfg.python -I (Join-Path $CloneRoot "ops\release\authority\mint_app_token.py") --app-id $cfg.app_id --installation-id $cfg.installation_id --key (Join-Path $home_ "key\app.pem") 2>$null | Out-String).Trim()
    $rc = $LASTEXITCODE; $ErrorActionPreference = $eap
    if ($rc -ne 0 -or -not $tok) { throw "the quant-merger App token could not be minted" }
    $env:GH_TOKEN = $tok
    $n = 0; if ($env:GIT_CONFIG_COUNT) { $n = [int]$env:GIT_CONFIG_COUNT }
    $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("x-access-token:$tok"))
    Set-Item -LiteralPath "env:GIT_CONFIG_KEY_$n" -Value "http.https://github.com/.extraheader"
    Set-Item -LiteralPath "env:GIT_CONFIG_VALUE_$n" -Value "AUTHORIZATION: basic $basic"
    $env:GIT_CONFIG_COUNT = "$($n + 1)"
    # GCM must not answer with zuck's stored login once the header is set
    $m = $n + 1
    Set-Item -LiteralPath "env:GIT_CONFIG_KEY_$m" -Value "credential.helper"
    Set-Item -LiteralPath "env:GIT_CONFIG_VALUE_$m" -Value ""
    $env:GIT_CONFIG_COUNT = "$($m + 1)"
    return $true
}
