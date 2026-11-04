# ONE-TIME INSTALL OF THE STATE PUBLISHER (ops/release/authority/LEVEL2.md step 2).
#
# zuck runs this ONCE, elevated, after creating the GitHub App "quant-state-publisher" (Contents:
# Read & write, Metadata: Read; no webhook; installed on the quant repository only) and
# downloading its private key. One argument: the App ID. Like the authority's installer it finds
# the key (the newest quant-state-publisher*.private-key.pem in Downloads, moved into the key
# folder), the installation id, and a machine-wide Python. It creates the local account
# `quant-publisher` (random password, never shown or stored), gives it READ access to the box
# checkout's .git only (never the worktree, so never data/secrets), clones LIVE, and registers the
# task Quant-StatePublisher (every 5 min, as quant-publisher). It needs the root pin that the
# authority installer wrote, re-pinned after the PR that added this file.

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $AppId,
    [string] $AppKey = "",
    [string] $Owner = "kingdemond434-cpu",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Home_ = "C:\opt\publisher",
    [string] $Src = "C:\opt\quant",
    [string] $Registry = "C:\opt\audit_registry"
)
$ErrorActionPreference = 'Stop'
$User = "quant-publisher"
$Key = Join-Path $Home_ "key"
$Clone = Join-Path $Home_ "repo"
function Step([string] $s) { Write-Host "== $s" -ForegroundColor Cyan }

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
if ($AppId -notmatch '^\d+$') { throw "AppId must be the App's number (App settings page, 'App ID'), not '$AppId'." }
if (-not (Test-Path (Join-Path $Registry "ROOT_PIN.json"))) { throw "Install the release authority first (ONE_TIME_AUTHORISATION.md)." }
$Python = (Get-Content -Raw "C:\opt\authority\config.json" | ConvertFrom-Json).python

Step "Account, folders and ACLs"
foreach ($d in @($Home_, $Key)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
$bytes = New-Object byte[] 30
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$pw = "Qp1!" + [Convert]::ToBase64String($bytes)
$sec = ConvertTo-SecureString $pw -AsPlainText -Force
if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $User -Password $sec -PasswordNeverExpires -AccountNeverExpires -Description "Box state publisher" | Out-Null
} else { Set-LocalUser -Name $User -Password $sec }
& icacls $Home_ /inheritance:r /grant:r "${User}:(OI)(CI)M" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
& icacls $Key /inheritance:r /grant:r "${User}:(OI)(CI)R" "SYSTEM:(OI)(CI)F" | Out-Null
# RX on .git makes its config readable to quant-publisher: refuse if it carries a credential
# (#650 audit SF4). Credentials belong in Windows Credential Manager, never in .git/config.
$gc = Get-Content -Raw -LiteralPath (Join-Path $Src ".git\config")
if ($gc -match '(?im)extraheader|^\s*\[credential|helper\s*=\s*store|insteadOf|https?://[^/\s@]+@') {
    throw "$Src\.git\config carries a credential or URL rewrite; remove it before granting quant-publisher read access."
}
& icacls $Src /grant "${User}:RX" | Out-Null                       # traverse only, this folder
& icacls (Join-Path $Src ".git") /grant "${User}:(OI)(CI)RX" /T /C /Q | Out-Null

Step "The App's private key"
if (-not $AppKey) {
    $pems = @(Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE "Downloads") -Filter "quant-state-publisher*.private-key.pem" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($pems.Count -gt 0) { $AppKey = $pems[0].FullName }
    if ($pems.Count -gt 1) { Write-Host "   $($pems.Count) keys found; using the NEWEST. Delete the older ones on the App's page afterwards." -ForegroundColor Yellow }
}
$appPem = Join-Path $Key "app.pem"
if ($AppKey -and (Test-Path -LiteralPath $AppKey)) {
    Write-Host "   using App key: $(Split-Path -Leaf $AppKey)"
    Move-Item -Force -LiteralPath $AppKey -Destination $appPem
} elseif (-not (Test-Path -LiteralPath $appPem)) {
    throw "No quant-state-publisher key in Downloads. On the App's page click 'Generate a private key', then run this again."
}
& icacls $appPem /inheritance:r /grant:r "${User}:R" "SYSTEM:F" | Out-Null

Step "Clone of LIVE"
if (-not (Test-Path (Join-Path $Clone ".git"))) {
    & git clone -q --no-checkout "https://github.com/$Repo.git" $Clone
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
}
& git -c safe.directory=* -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
& git -c safe.directory=* -C $Clone checkout -q -f --detach "origin/$Live"
if (-not (Test-Path (Join-Path $Clone "ops\release\publisher\publish.py"))) { throw "LIVE has no ops/release/publisher yet" }
& icacls $Clone /setowner $User /T /C /Q | Out-Null

Step "Installation id"
$Inst = (& $Python -I (Join-Path $Clone "ops\release\authority\mint_app_token.py") --app-id $AppId --key $appPem --find-installation $Owner)
if ($LASTEXITCODE -ne 0 -or -not $Inst) { throw "The App is not installed. On the App page click 'Install App', choose the quant repository only, then run this again." }
@{ app_id = $AppId; installation_id = "$Inst".Trim(); python = $Python } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Home_ "config.json") -Encoding UTF8

Step "Scheduled task Quant-StatePublisher"
$runner = Join-Path $Home_ "run_publisher.ps1"
Copy-Item -Force (Join-Path $Clone "ops\release\publisher\run_publisher.ps1") $runner
$act = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ("-NoProfile -ExecutionPolicy Bypass -File `"$runner`"")
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "Quant-StatePublisher" -Action $act -Trigger $trg -Settings $set -User $User -Password $pw -Force | Out-Null
$pw = $null; $sec = $null
Write-Host ""
Write-Host "DONE. First pass log: $Home_\publisher.log (within 5 min)." -ForegroundColor Green
