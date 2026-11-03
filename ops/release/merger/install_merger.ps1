# ONE-TIME INSTALL OF THE BOX'S MERGER IDENTITY (ops/release/authority/LEVEL2.md step 3).
#
# zuck runs this ONCE, elevated, after creating the GitHub App "quant-merger" (Contents, Pull
# requests and Workflows: Read & write; Metadata: Read; no webhook; installed on the quant
# repository only) and downloading its key. One argument: the App ID. It moves the newest
# quant-merger*.private-key.pem from any user's Downloads into C:\opt\merger\key (Administrators
# and SYSTEM only), finds the installation id, and writes config.json. From the next pass on, the
# gate and the sign train use the App instead of zuck's gh login. Delete C:\opt\merger\config.json
# to go back.
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $AppId,
    [string] $AppKey = "",
    [string] $Owner = "kingdemond434-cpu",
    [string] $Clone = "C:\ProgramData\QuantBox\gate-repo"
)
$ErrorActionPreference = 'Stop'
$Home_ = "C:\opt\merger"; $Key = Join-Path $Home_ "key"
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
if ($AppId -notmatch '^\d+$') { throw "AppId must be the App's number, not '$AppId'." }
$Python = (Get-Content -Raw "C:\opt\authority\config.json" | ConvertFrom-Json).python
foreach ($d in @($Home_, $Key)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
& icacls $Home_ /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null
if (-not $AppKey) {
    $pems = @(Get-ChildItem C:\Users\*\Downloads -Filter "quant-merger*.private-key.pem" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($pems.Count -gt 0) { $AppKey = $pems[0].FullName }
    if ($pems.Count -gt 1) { Write-Host "   $($pems.Count) keys found; using the NEWEST. Delete the older ones on the App's page afterwards." -ForegroundColor Yellow }
}
$appPem = Join-Path $Key "app.pem"
if ($AppKey -and (Test-Path -LiteralPath $AppKey)) {
    Write-Host "   using App key: $(Split-Path -Leaf $AppKey)"
    Move-Item -Force -LiteralPath $AppKey -Destination $appPem
} elseif (-not (Test-Path -LiteralPath $appPem)) {
    throw "No quant-merger key found in any Downloads folder. Generate one on the App's page, then run this again."
}
$Inst = (& $Python -I (Join-Path $Clone "ops\release\authority\mint_app_token.py") --app-id $AppId --key $appPem --find-installation $Owner)
if ($LASTEXITCODE -ne 0 -or -not $Inst) { throw "The App is not installed. On the App page click 'Install App', choose the quant repository only, then run this again." }
@{ app_id = $AppId; installation_id = "$Inst".Trim(); python = $Python } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Home_ "config.json") -Encoding UTF8
Write-Host "DONE. The gate and the sign train use quant-merger from their next pass." -ForegroundColor Green
