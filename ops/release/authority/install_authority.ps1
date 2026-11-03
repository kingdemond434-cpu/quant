# ONE-TIME INSTALL OF THE RELEASE AUTHORITY ON THE BOX (ops/release/authority/ONE_TIME_AUTHORISATION.md).
#
# zuck runs this ONCE, in an ELEVATED PowerShell, after creating the read-only GitHub App and
# downloading its private key. It is the only step that creates the authority's identity, so no
# Claude session runs it. One argument: the App ID (the number on the App's settings page). It
# finds the rest itself:
#   * the App's private key: the newest *.private-key.pem in your Downloads folder (or -AppKey);
#     it is MOVED into the key folder, so no copy stays readable elsewhere;
#   * the installation id, by asking GitHub as the App (fails clearly if the App is not installed);
#   * a machine-wide Python 3 with `cryptography` (Program Files), and a gh.exe it copies into
#     C:\opt\authority\bin so the authority's own account can run it.
# Then it creates the local account `quant-authority` (random password, never shown or stored),
# the folders and ACLs, the Ed25519 signing key INSIDE that account's key folder, the public key,
# the root pin, and the scheduled task Quant-ReleaseAuthority (every 10 min, as quant-authority).
# It does NOT turn the gate's path on (that is -Activate, or the setx lines in the pack).

[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $AppId,
    [string] $AppKey = "",
    [string] $Owner = "kingdemond434-cpu",
    [string] $Repo = "kingdemond434-cpu/quant",
    [string] $Live = "claude/llm-auto-upgrade-verify-gcjac3",
    [string] $Home_ = "C:\opt\authority",
    [string] $Registry = "C:\opt\audit_registry",
    [string] $Python = "",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    [switch] $Activate
)
$ErrorActionPreference = 'Stop'
$User = "quant-authority"
$Key = Join-Path $Home_ "key"
$Bin = Join-Path $Home_ "bin"
$Clone = Join-Path $Home_ "repo"
$Att = Join-Path $Registry "attestations"
function Step([string] $s) { Write-Host "== $s" -ForegroundColor Cyan }

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
if ($AppId -notmatch '^\d+$') { throw "AppId must be the App's number (App settings page, 'App ID'), not '$AppId'." }

Step "Python with cryptography"
if (-not $Python) {
    foreach ($c in @('C:\Program Files\Python314\python.exe', 'C:\Program Files\Python313\python.exe', 'C:\Program Files\Python312\python.exe', 'C:\Program Files\Python311\python.exe')) {
        if (Test-Path -LiteralPath $c) { $Python = $c; break }
    }
}
if (-not $Python) { throw "No machine-wide Python under C:\Program Files. Install Python 3 for all users, then run this again." }
& $Python -c "import cryptography" 2>$null
# pinned, wheels only: this runs elevated (#643 audit SF2)
if ($LASTEXITCODE -ne 0) { & $Python -m pip install --quiet --only-binary :all: "cryptography==50.0.1"; if ($LASTEXITCODE -ne 0) { throw "pip install cryptography failed" } }
Write-Host "   $Python"

Step "Folders and ACLs"
foreach ($d in @($Home_, $Key, $Bin, $Att)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
# works in Windows PowerShell 5.1 and pwsh 7 alike (#643 audit SF1)
$bytes = New-Object byte[] 30
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$pw = "Qa1!" + [Convert]::ToBase64String($bytes)
$sec = ConvertTo-SecureString $pw -AsPlainText -Force
if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $User -Password $sec -PasswordNeverExpires -AccountNeverExpires -Description "Release authority signer" | Out-Null
} else {
    Set-LocalUser -Name $User -Password $sec
}
& icacls $Key /inheritance:r /grant:r "${User}:(OI)(CI)M" "SYSTEM:(OI)(CI)F" | Out-Null
& icacls $Att /inheritance:r /grant:r "${User}:(OI)(CI)M" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)RX" | Out-Null
& icacls $Home_ /inheritance:r /grant:r "${User}:(OI)(CI)M" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null

Step "The App's private key"
if (-not $AppKey) {
    $dl = Join-Path $env:USERPROFILE "Downloads"
    $AppKey = (Get-ChildItem -LiteralPath $dl -Filter "*.private-key.pem" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}
$appPem = Join-Path $Key "app.pem"
if ($AppKey -and (Test-Path -LiteralPath $AppKey)) {
    Move-Item -Force -LiteralPath $AppKey -Destination $appPem
} elseif (-not (Test-Path -LiteralPath $appPem)) {
    throw "No App private key found. On the App's settings page click 'Generate a private key' (it downloads a .pem), then run this again."
}

Step "Checkout of LIVE"
if (-not (Test-Path (Join-Path $Clone ".git"))) {
    & git clone -q --no-checkout "https://github.com/$Repo.git" $Clone
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
}
& git -c safe.directory=* -C $Clone fetch -q --no-tags origin "+refs/heads/${Live}:refs/remotes/origin/${Live}"
& git -c safe.directory=* -C $Clone checkout -q -f --detach "origin/$Live"
if (-not (Test-Path (Join-Path $Clone "ops\release\authority\authority.py"))) { throw "LIVE has no ops/release/authority yet" }
Copy-Item -Force -LiteralPath $Gh -Destination (Join-Path $Bin "gh.exe")

Step "Installation id (asked of GitHub as the App)"
$Inst = (& $Python -I (Join-Path $Clone "ops\release\authority\mint_app_token.py") --app-id $AppId --key $appPem --find-installation $Owner)
if ($LASTEXITCODE -ne 0 -or -not $Inst) { throw "The App is not installed. On the App page click 'Install App', choose the quant repository only, then run this again." }
$Inst = "$Inst".Trim()
Write-Host "   installation $Inst"
@{ app_id = $AppId; installation_id = $Inst; python = $Python } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Home_ "config.json") -Encoding UTF8

Step "Signing key, generated as $User"
$cred = New-Object System.Management.Automation.PSCredential($User, $sec)
$gen = Join-Path $Home_ "keygen.py"
@"
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric import ed25519
import base64, pathlib
k = ed25519.Ed25519PrivateKey.generate()
pathlib.Path(r'$Key\authority.pem').write_bytes(k.private_bytes(s.Encoding.PEM, s.PrivateFormat.PKCS8, s.NoEncryption()))
pathlib.Path(r'$Home_\authority.pub').write_text(base64.b64encode(k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)).decode())
"@ | Set-Content -LiteralPath $gen -Encoding ASCII
if (-not (Test-Path (Join-Path $Key "authority.pem"))) {
    $p = Start-Process -FilePath $Python -ArgumentList @("-I", "`"$gen`"") -Credential $cred -Wait -PassThru -LoadUserProfile -WorkingDirectory $Home_
    if ($p.ExitCode -ne 0) { throw "key generation as $User failed ($($p.ExitCode))" }
}
Remove-Item -LiteralPath $gen -Force
& icacls (Join-Path $Key "app.pem") /inheritance:r /grant:r "${User}:R" "SYSTEM:F" | Out-Null
Copy-Item -Force (Join-Path $Home_ "authority.pub") (Join-Path $Registry "authority.pub")
& icacls (Join-Path $Registry "authority.pub") /inheritance:r /grant:r "Administrators:F" "SYSTEM:F" "Users:R" | Out-Null

Step "Root pin"
& $Python -I (Join-Path $Clone "ops\release\authority\pin_root.py") --write (Join-Path $Registry "ROOT_PIN.json")
& icacls (Join-Path $Registry "ROOT_PIN.json") /inheritance:r /grant:r "Administrators:F" "SYSTEM:F" "Users:R" | Out-Null
& icacls $Clone /setowner $User /T /C /Q | Out-Null

Step "Scheduled task Quant-ReleaseAuthority"
$runner = Join-Path $Home_ "run_authority.ps1"
Copy-Item -Force (Join-Path $Clone "ops\release\authority\run_authority.ps1") $runner
$act = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ("-NoProfile -ExecutionPolicy Bypass -File `"$runner`"")
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)
$set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "Quant-ReleaseAuthority" -Action $act -Trigger $trg -Settings $set -User $User -Password $pw -Force | Out-Null
$pw = $null; $sec = $null; $cred = $null

if ($Activate) {
    Step "Gate path ON (machine env vars)"
    [Environment]::SetEnvironmentVariable("QUANT_AUTHORITY_PUBKEY", (Join-Path $Registry "authority.pub"), "Machine")
    [Environment]::SetEnvironmentVariable("QUANT_AUTHORITY_ATTESTATIONS", $Att, "Machine")
    [Environment]::SetEnvironmentVariable("QUANT_AUTHORITY_ROOT_PIN", (Join-Path $Registry "ROOT_PIN.json"), "Machine")
}
Write-Host ""
Write-Host "DONE. Public key: $(Get-Content (Join-Path $Registry 'authority.pub'))" -ForegroundColor Green
Write-Host "First pass log: $Home_\authority.log (within 10 min)."
if ($Activate) {
    # machine env vars reach a process only when it starts (#643 audit SF4)
    Write-Host "The gate reads attestations from its next start: the 10-minute Quant-WorkflowGate run picks the new variables up by itself."
} else { Write-Host "The gate does not read attestations yet: run again with -Activate to turn it on." }
# What the gate trusts lives only in $Registry (authority.pub, ROOT_PIN.json: Administrators-write);
# nothing the gate reads may ever be placed under $Home_, which quant-authority can modify (SF3).
