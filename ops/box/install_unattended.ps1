# MAKE THE BOX NEED NOBODY AFTER A REBOOT, AND MERGE WORKFLOW-FILE PRs ITSELF (2026-10-28).
#
# zuck: "I wish we could make it so even these become automated not needing me". Registers four
# tasks for the desk user (interactive, elevated, the way the bridge watchdog and the FTMO follower
# already run), all from admin-only copies under C:\ProgramData\QuantBox\bin:
#
#   Quant-BootSession   at logon:        ops\box\unattended_boot.ps1 -Mode Logon
#   Quant-BootRecord    every 10 min:    ops\box\unattended_boot.ps1 -Mode Record
#   Quant-WorkflowGate  logon + 10 min:  ops\box\workflow_gate.ps1
#   Quant-SignTrain     logon + 10 min:  ops\box\sign_train_leg.ps1  (the audit signs, D-20261027-003)
#
# THE DESK USER. Run by hand, the tasks are this user's. Run by the SYSTEM adopter
# (ops\box\apply_installers.py, a `desk_user` row), -User names the account: SYSTEM's own
# USERNAME is the machine account, so without -User a SYSTEM run refuses rather than register
# interactive tasks nobody logs on as. -User is DOMAIN\name or name, nothing else.
#
# The two things only zuck can give (the desktop logon after a reboot, and the gh `workflow`
# scope) are reported and staged by ops\box\owner_steps.ps1, never by this installer, so this
# one carries no credential step and the SYSTEM adopter may run it (zuck 2026-11-17 19:56Z).
#
# Idempotent; touches only these four tasks and C:\ProgramData\QuantBox.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\box\install_unattended.ps1 [-User DOMAIN\name]

[CmdletBinding()]
param(
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $User = ""
)
$ErrorActionPreference = 'Stop'
$BinDir = Join-Path $Root "bin"
$LogDir = Join-Path $Root "logs"
$ToolDir = Join-Path $Root "tools"
$adm = 'S-1-5-32-544'; $sys = 'S-1-5-18'; $usr = 'S-1-5-32-545'

# THE ROOT IS ADMIN-ONLY FROM ITS FIRST BYTE (the bridge watchdog's audited pattern): a new root is
# created with its locked ACL in one call; an existing one that Administrators/SYSTEM do not own is
# refused, never taken over; no junction is followed anywhere under it.
if (-not (Test-Path -LiteralPath $Root)) {
    $sec = New-Object System.Security.AccessControl.DirectorySecurity
    $sec.SetAccessRuleProtection($true, $false)
    $sec.SetOwner((New-Object System.Security.Principal.SecurityIdentifier $adm))
    foreach ($ace in @(@($adm, 'FullControl'), @($sys, 'FullControl'), @($usr, 'ReadAndExecute'))) {
        $sec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier $ace[0]), $ace[1], 'ContainerInherit, ObjectInherit', 'None', 'Allow')))
    }
    $null = [System.IO.Directory]::CreateDirectory($Root, $sec)
}
$owner = (New-Object System.Security.Principal.NTAccount((Get-Acl -LiteralPath $Root).Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
if ($owner -notin @($adm, $sys)) { throw "$Root is owned by $owner, not Administrators/SYSTEM; delete it as an administrator and re-run" }
foreach ($c in @(Get-Item -LiteralPath $Root -Force) + @(Get-ChildItem -LiteralPath $Root -Force -Recurse)) {
    if ($c.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "$($c.FullName) is a junction or symlink; not installing" }
}
foreach ($d in @($BinDir, $LogDir, $ToolDir)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
foreach ($path in @($Root) + @(Get-ChildItem -LiteralPath $Root -Force -Recurse | ForEach-Object { $_.FullName })) {
    foreach ($a in (Get-Acl -LiteralPath $path).Access | Where-Object { $_.AccessControlType -eq 'Allow' }) {
        $sid = $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        $write = [int64]$a.FileSystemRights -band ([int64][System.Security.AccessControl.FileSystemRights]"Write, Delete, ChangePermissions, TakeOwnership" -bor 0x50000000)
        if ($sid -notin @($adm, $sys, $usr) -or ($sid -eq $usr -and $write -ne 0)) {
            throw "$path grants $($a.IdentityReference) more than read; not installing"
        }
    }
}

foreach ($name in @('unattended_boot.ps1', 'workflow_gate.ps1', 'sign_train_leg.ps1')) {
    $src = Join-Path $PSScriptRoot $name
    if (-not (Test-Path -LiteralPath $src)) { throw "$name missing at $src" }
    $dst = Join-Path $BinDir $name
    Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
    Copy-Item -LiteralPath $src -Destination $dst
    "copied {0} (sha256 {1})" -f $dst, (Get-FileHash $dst -Algorithm SHA256).Hash.ToLower().Substring(0, 12)
}

if ($User) {
    if ($User -notmatch '^([A-Za-z0-9._-]{1,64}\\)?[A-Za-z0-9._-]{1,64}$') { throw "-User '$User' is not DOMAIN\name" }
    $user = $User
} else {
    $me = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    if ($me -eq 'S-1-5-18') { throw "run as SYSTEM without -User: refusing to register interactive tasks for the machine account" }
    $user = "{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME
}
"tasks are for $user"
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
function Every10 {
    # A DAILY trigger repeating for one day, never a long -Once (one expired on this box, 2026-09-21).
    $t = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date)
    $t.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date) `
        -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
    $t
}
function Add-QuantTask([string] $name, [string] $script, [string] $extra, $triggers, [int] $limitMin, [string] $why) {
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument `
        ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" {1}' -f (Join-Path $BinDir $script), $extra)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes $limitMin) -MultipleInstances IgnoreNew
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $name -Confirm:$false }
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Principal $principal `
        -Settings $settings -Description $why | Out-Null
    "registered $name"
}
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
Add-QuantTask 'Quant-BootSession' 'unattended_boot.ps1' '-Mode Logon' @($atLogon) 10 `
    'After a logon: start the MT5 terminals that were running before the reboot (never Fusion; never a second copy); lock the console session.'
Add-QuantTask 'Quant-BootRecord' 'unattended_boot.ps1' '-Mode Record' @(Every10) 5 `
    'Record which MT5 terminals run in this desktop session, for Quant-BootSession after a reboot.'
Add-QuantTask 'Quant-WorkflowGate' 'workflow_gate.ps1' '' @($atLogon, (Every10)) 30 `
    'Merge audit-CLEARed, CI-green PRs into LIVE (no label needed; workflow-file PRs too), with zuck''s gh login, from a clean checkout of LIVE.'
Add-QuantTask 'Quant-SignTrain' 'sign_train_leg.ps1' '' @($atLogon, (Every10)) 20 `
    'Sign moved sealed files whose CLEAR row is committed in SEAL_CLEARS.jsonl, and open the sign-train PR into LIVE, from a clean checkout of LIVE.'
Start-ScheduledTask -TaskName 'Quant-BootRecord'

