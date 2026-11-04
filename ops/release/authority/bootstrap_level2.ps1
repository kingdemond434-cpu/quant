# THE ONE-TIME LEVEL 2 BOOTSTRAP OF THE RELEASE AUTHORITY (ops/release/authority/LEVEL2.md).
#
# The owner runs this ONCE, in an elevated PowerShell on the trading box, signed in to GitHub in
# his browser and with his gh login still on the box. Each GitHub act in it is HIS, done because
# he started it: merging #650 (ROOT: the authority can never approve a change to itself), the
# root re-pin, creating and installing two Apps, the seal environment, the rulesets, and logging
# his own credential off the box. Nothing here is ever run by an agent or a scheduled task.
#
# WHAT HE DOES WHILE IT RUNS (every other step is the script's):
#   * 1 tick + 2 clicks: the authority App's "Commit statuses: Read and write", Save, then Accept
#     on the installation (GitHub shows both pages; there is no API for an App's permissions);
#   * 2 clicks per new App, twice: "Create GitHub App" on the page the script opens (the
#     manifest fixes every permission; the key goes straight into the App's own key folder, no
#     download), then "Install" on quant only.
#
# It is resumable: every step checks whether it is already done, so after any stop the same
# command continues where it left off. It enforces nothing until the last step, and that step
# runs only when the checker proves every LIVE writer converted and GitHub reports the rule.
[CmdletBinding()]
param(
    [string] $Owner = "kingdemond434-cpu",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [int] $Pr = 650,
    [string] $Registry = "C:\opt\audit_registry",
    [string] $AuthHome = "C:\opt\authority",
    [string] $Work = "C:\opt\bootstrap",
    [switch] $KeepOwnerLogin
)
$ErrorActionPreference = 'Stop'
function Step([string] $s) { Write-Host "`n== $s" -ForegroundColor Cyan }
function Wait-Until([scriptblock] $Test, [int] $Minutes, [string] $What) {
    $end = (Get-Date).AddMinutes($Minutes)
    while ((Get-Date) -lt $end) { if (& $Test) { return } ; Start-Sleep -Seconds 15 }
    throw "Timed out after $Minutes min waiting for: $What. Nothing past this point was done; run the same command again to continue."
}

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
$cfg = Get-Content -Raw (Join-Path $AuthHome "config.json") | ConvertFrom-Json
$Python = $cfg.python
$Clone = Join-Path $AuthHome "repo"
$env:GH_REPO = $Repo
$me = (& gh api user --jq .login 2>$null)
if ($LASTEXITCODE -ne 0 -or "$me".Trim() -ne $Owner) { throw "gh is not signed in as $Owner here (got '$me'). This script is the owner's own act." }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
& icacls $Work /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
function Py { & $Python -I @args }
function Refresh-Clone {
    & git -c safe.directory=* -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
    & git -c safe.directory=* -C $Clone checkout -q -f --detach "origin/$Live"
    if ($LASTEXITCODE -ne 0) { throw "could not check out LIVE in $Clone" }
}

Step "1/8  #$Pr on LIVE (ROOT: merged by the owner, at the exact head the audit cleared)"
$merged = (& gh api "repos/$Repo/pulls/$Pr" --jq .merged)
if ("$merged".Trim() -ne "true") {
    Refresh-Clone
    $head = (Py (Join-Path $Clone "ops\release\authority\bootstrap_github.py") --repo $Repo ready --pr $Pr | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0) { throw "#$Pr is not ready to merge (see NOT READY above). Nothing was changed." }
    & gh api -X PUT "repos/$Repo/pulls/$Pr/merge" -f sha="$head".Trim() -f merge_method=merge | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "GitHub refused the merge of #$Pr at $head." }
    Write-Host "   merged #$Pr at $head"
}
Refresh-Clone
if (-not (Test-Path (Join-Path $Clone "ops\release\authority\bootstrap_github.py"))) { throw "LIVE does not carry #$Pr yet." }
$Here = Join-Path $Clone "ops\release\authority"

Step "2/8  Root re-pin from a clean checkout of LIVE"
& $Python -I (Join-Path $Here "pin_root.py") --write (Join-Path $Registry "ROOT_PIN.json")
if ($LASTEXITCODE -ne 0) { throw "pin_root failed" }
& icacls (Join-Path $Registry "ROOT_PIN.json") /inheritance:r /grant:r "Administrators:F" "SYSTEM:F" "Users:R" | Out-Null
Copy-Item -Force (Join-Path $Here "run_authority.ps1") (Join-Path $AuthHome "run_authority.ps1")
& icacls $Clone /setowner "quant-authority" /T /C /Q | Out-Null

Step "3/8  The authority posts the release-authority status"
$flag = Join-Path $Registry "POST_STATUS"
$log = Join-Path $AuthHome "authority.log"
if (-not (Select-String -LiteralPath $log -Pattern '\[status (success|failure|pending)\]' -Quiet -ErrorAction SilentlyContinue)) {
    Write-Host "   On the page that opens: your release-authority App -> Permissions & events ->" -ForegroundColor Yellow
    Write-Host "   Repository permissions -> Commit statuses: Read and write, AND Administration: Read-only" -ForegroundColor Yellow
    Write-Host "   (it lets the authority see who may bypass the ruleset) -> Save changes." -ForegroundColor Yellow
    Write-Host "   Then on the installations page: Configure / Review request -> Accept new permissions." -ForegroundColor Yellow
    Start-Process "https://github.com/settings/apps"
    Read-Host "   Press Enter once both are saved"
    Start-Process "https://github.com/settings/installations"
    New-Item -ItemType File -Force -Path $flag | Out-Null
    $mark = (Get-Item -LiteralPath $log -ErrorAction SilentlyContinue).Length
    Start-ScheduledTask -TaskName "Quant-ReleaseAuthority"
    Wait-Until -Minutes 30 -What "a status the authority posted (authority.log '[status ...]')" -Test {
        Start-ScheduledTask -TaskName "Quant-ReleaseAuthority" -ErrorAction SilentlyContinue
        $t = Get-Content -LiteralPath $log -Raw -ErrorAction SilentlyContinue
        if (-not $t) { return $false }
        $new = $t.Substring([Math]::Min([int]$mark, $t.Length))
        if ($new -match 'status not posted') { Write-Host "   not yet: the status was refused (permission not accepted yet?)" }
        return $new -match '\[status (success|failure|pending)\]'
    }
}
Write-Host "   the authority posts its status"

function New-BoxApp([string] $Kind, [string] $ConfigPath) {
    $out = Join-Path $Work "$Kind.json"
    $pem = Join-Path $Work "$Kind.pem"
    if (Test-Path -LiteralPath $ConfigPath) { return (Get-Content -Raw $ConfigPath | ConvertFrom-Json).app_id }
    if (-not (Test-Path -LiteralPath $out)) {
        Py (Join-Path $Here "app_manifest.py") --kind $Kind --pem $pem --out $out | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "the $Kind App was not created (see above)." }
    }
    $app = Get-Content -Raw $out | ConvertFrom-Json
    Write-Host "   On the page that opens, choose 'Only select repositories' -> quant -> Install." -ForegroundColor Yellow
    Start-Process "https://github.com/apps/$($app.slug)/installations/new"
    Wait-Until -Minutes 30 -What "$($app.slug) installed on quant" -Test {
        $i = (Py (Join-Path $Here "mint_app_token.py") --app-id $app.id --key $pem --find-installation $Owner 2>$null)
        return ($LASTEXITCODE -eq 0 -and $i)
    }
    return $app.id
}

Step "4/8  The merger App (no admin, no statuses)"
$mergerId = New-BoxApp "merger" "C:\opt\merger\config.json"
if (-not (Test-Path "C:\opt\merger\config.json")) {
    & (Join-Path $Clone "ops\release\merger\install_merger.ps1") -AppId $mergerId -AppKey (Join-Path $Work "merger.pem") -Clone $Clone | Out-Host
}

Step "5/8  The state publisher App, and CI's LIVE-only seal environment"
$stateId = New-BoxApp "publisher" "C:\opt\publisher\config.json"
$statePem = Join-Path $Work "publisher.pem"
$stateSlug = (Get-Content -Raw (Join-Path $Work "publisher.json") -ErrorAction SilentlyContinue | ConvertFrom-Json).slug
if (Test-Path -LiteralPath $statePem) {
    $envBody = '{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
    $envBody | & gh api -X PUT "repos/$Repo/environments/live-seal" --input - | Out-Null
    $pols = (& gh api "repos/$Repo/environments/live-seal/deployment-branch-policies" | ConvertFrom-Json).branch_policies
    foreach ($p in @($pols)) { if ($p -and $p.name -ne $Live) { & gh api -X DELETE "repos/$Repo/environments/live-seal/deployment-branch-policies/$($p.id)" | Out-Null } }
    if (-not (@($pols) | Where-Object { $_.name -eq $Live })) {
        & gh api -X POST "repos/$Repo/environments/live-seal/deployment-branch-policies" -f name=$Live -f type=branch | Out-Null
    }
    # The same key as the box publisher's: GitHub gives a manifest-made App one key, and a second
    # one is a page click. Its exposure is LIVE's own ci.yml (environment admits LIVE alone).
    Get-Content -Raw -LiteralPath $statePem | & gh secret set STATE_APP_KEY --env live-seal --repo $Repo
    & gh variable set STATE_APP_ID --env live-seal --repo $Repo --body "$stateId"
    if ($LASTEXITCODE -ne 0) { throw "could not configure the live-seal environment" }
    & (Join-Path $Clone "ops\release\publisher\install_publisher.ps1") -AppId $stateId -AppKey $statePem
}
@{ login = "$stateSlug[bot]" } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Registry "STATE_APP.json") -Encoding UTF8

Step "6/8  Every LIVE writer converted, observed"
Start-ScheduledTask -TaskName "Quant-StatePublisher"
Wait-Until -Minutes 20 -What "a clean Quant-StatePublisher pass" -Test {
    $i = Get-ScheduledTaskInfo -TaskName "Quant-StatePublisher"
    return ($i.LastTaskResult -eq 0 -and $i.LastRunTime -gt (Get-Date).AddMinutes(-25))
}
$probe = (Py (Join-Path $Here "mint_app_token.py") --app-id $mergerId --key "C:\opt\merger\key\app.pem" --installation-id (Get-Content -Raw "C:\opt\merger\config.json" | ConvertFrom-Json).installation_id)
if ($LASTEXITCODE -ne 0 -or -not $probe) { throw "the merger cannot mint a token; enforcement NOT applied" }
$probe = $null
Write-Host "   publisher pass clean; merger token mints; gate and sign train use it from their next pass"

Step "7/8  The two rulesets: checked, applied, read back from GitHub"
Py (Join-Path $Here "bootstrap_github.py") --repo $Repo rulesets --state-app-id $stateId --apply
if ($LASTEXITCODE -ne 0) { throw "the rulesets were not confirmed active (see above)." }
# The authority must see it too, with its OWN token (it needs Administration: read for the bypass
# list). Until it does, the gate and merger simply stay ROOT: safe, and said so here.
$mark = (Get-Item -LiteralPath $log).Length
try {
    Wait-Until -Minutes 25 -What "the authority reading 'level 2: ENFORCED'" -Test {
        Start-ScheduledTask -TaskName "Quant-ReleaseAuthority" -ErrorAction SilentlyContinue
        $t = Get-Content -LiteralPath $log -Raw
        return $t.Substring([Math]::Min([int]$mark, $t.Length)) -match 'level 2: ENFORCED'
    }
    Write-Host "   the authority reads the rule as enforced: gate and merger changes are CONTROLLER now"
} catch {
    Write-Host "   GitHub enforces the rule, but the authority cannot confirm it yet (Administration: Read-only not accepted?). Gate and merger changes stay ROOT until it can; nothing is unsafe." -ForegroundColor Yellow
}

Step "8/8  The owner's credential leaves the box"
if ($KeepOwnerLogin) {
    Write-Host "   -KeepOwnerLogin: your gh login stays. Every LIVE write still needs the authority's status." -ForegroundColor Yellow
} else {
    & gh auth logout --hostname github.com 2>$null | Out-Null
    foreach ($t in @(& cmdkey /list | Select-String -Pattern 'Target:\s*(\S*github\.com\S*)' | ForEach-Object { $_.Matches[0].Groups[1].Value })) {
        & cmdkey /delete:$t | Out-Null; Write-Host "   removed credential $t"
    }
    $other = @(Get-ChildItem "C:\Users\*\AppData\Roaming\GitHub CLI\hosts.yml", "C:\Windows\System32\config\systemprofile\AppData\Roaming\GitHub CLI\hosts.yml" -ErrorAction SilentlyContinue)
    foreach ($h in $other) { Remove-Item -Force -LiteralPath $h.FullName; Write-Host "   removed gh login $($h.FullName)" }
}
Remove-Item -Force -LiteralPath (Join-Path $Work "merger.pem"), $statePem -ErrorAction SilentlyContinue
Write-Host "`nDONE. GitHub refuses any LIVE merge the authority did not pass; master and production move only by CI's promote." -ForegroundColor Green
Write-Host "Routine and protected changes now need no owner act. Only a change to the authority itself (ROOT) does."
