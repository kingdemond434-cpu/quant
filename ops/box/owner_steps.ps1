# THE TWO THINGS ONLY ZUCK CAN GIVE THE BOX, REPORTED (AND ONE STAGED), NEVER SET (2026-10-28).
#
# Split out of ops\box\install_unattended.ps1 on 2026-11-17 so that installer carries no
# credential step and the SYSTEM adopter may run it (zuck 2026-11-17 19:56Z: no more one-time admin
# installs, but codes and passwords stay his). This file is NEVER a row of
# ops\box\auto_installers.json; zuck (or a session he asks) runs it by hand, in his own session.
#
#   AUTO-LOGON. The MT5 terminals need a logged-on desktop (see unattended_boot.ps1), so a reboot
#   needs a logon. Windows auto-logon gives one without a person. This file never sets it and
#   never sees the password: with -StageAutologon it downloads Microsoft's Sysinternals Autologon
#   (checked: Authenticode signature valid and signed by Microsoft) to C:\ProgramData\QuantBox\tools,
#   and zuck runs it ONCE in RDP, typing the Administrator password into its dialog. It stores the
#   password as an LSA secret, not as plain text in the registry. A plain-text DefaultPassword
#   value, an AutoLogonCount (which turns auto-logon off after N logons) or a logon banner (which
#   halts auto-logon at the banner) are reported as problems.
#
#   THE `workflow` SCOPE on zuck's gh login, which merging workflow-file PRs needs. If missing, zuck runs
#   once:  gh auth refresh -h github.com -s workflow
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\box\owner_steps.ps1 [-StageAutologon]

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Gh = "C:\Users\Administrator\tools\gh\bin\gh.exe",
    [switch] $StageAutologon
)
$ErrorActionPreference = 'Stop'
$ToolDir = Join-Path $Root "tools"
if ($StageAutologon) {
    if (-not (Test-Path -LiteralPath $Root)) { throw "$Root is absent: run ops\box\install_unattended.ps1 first (it creates the admin-only root)" }
    New-Item -ItemType Directory -Force -Path $ToolDir | Out-Null
}
if ($StageAutologon) {
    $zip = Join-Path $ToolDir 'AutoLogon.zip'
    $out = Join-Path $ToolDir 'AutoLogon'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://download.sysinternals.com/files/AutoLogon.zip' -OutFile $zip
    Remove-Item -LiteralPath $out -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $zip -DestinationPath $out
    $exe = Join-Path $out 'Autologon64.exe'
    $sig = Get-AuthenticodeSignature -LiteralPath $exe
    if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
        Remove-Item -LiteralPath $out, $zip -Recurse -Force
        throw "Autologon64.exe signature is $($sig.Status) / $($sig.SignerCertificate.Subject): deleted, not staged"
    }
    "staged $exe (Microsoft-signed)"
}

# ---------------------------------------------------------------- what zuck still has to give
# Value NAMES only for the password: its presence is the finding; its content is never read.
$wlKey = Get-Item -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
$wlNames = @($wlKey.GetValueNames())
$wl = @{ AutoAdminLogon = $wlKey.GetValue('AutoAdminLogon'); DefaultUserName = $wlKey.GetValue('DefaultUserName');
         AutoLogonCount = $wlKey.GetValue('AutoLogonCount') }
$pol = Get-ItemProperty -LiteralPath 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction SilentlyContinue
$problems = @()
if ("$($wl.AutoAdminLogon)" -ne '1') { $problems += 'auto-logon is OFF' }
elseif ("$($wl.DefaultUserName)" -ine $env:USERNAME) { $problems += "auto-logon is for '$($wl.DefaultUserName)', not $env:USERNAME" }
if ($wlNames -contains 'DefaultPassword') { $problems += 'a PLAIN-TEXT DefaultPassword is in the registry: re-run Autologon64.exe (it moves it to an LSA secret)' }
if ($null -ne $wl.AutoLogonCount) { $problems += "AutoLogonCount=$($wl.AutoLogonCount) will switch auto-logon off" }
if ($pol -and ("$($pol.legalnoticecaption)$($pol.legalnoticetext)").Trim()) { $problems += 'a logon banner (legalnotice) halts auto-logon at the banner' }
if ($problems.Count -eq 0) { "AUTO-LOGON: ON for $($wl.DefaultUserName)" }
else {
    "AUTO-LOGON NOT READY: " + ($problems -join '; ')
    "  zuck, once, in RDP: run $(Join-Path $ToolDir 'AutoLogon\Autologon64.exe'), type the Administrator password, click Enable."
}
$ErrorActionPreference = 'Continue'
$scopes = (& $Gh auth status -h github.com 2>&1 | Out-String) -split "`n" | Where-Object { $_ -match 'Token scopes' } | Select-Object -First 1
if ($scopes -match "'workflow'") { "GH WORKFLOW SCOPE: present" }
else { "GH WORKFLOW SCOPE: MISSING ($($scopes.Trim())). zuck, once:  $Gh auth refresh -h github.com -s workflow" }
