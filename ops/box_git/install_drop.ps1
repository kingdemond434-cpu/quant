<#
.SYNOPSIS
  Connect the release loop to the private drop repository (ops/box_git/drop_pull.py), once.

.DESCRIPTION
  Principal 2026-11-20 16:58Z: nothing on the box relies on Claude. After this runs, every
  QuantForge-Loop pass pulls new packets from the drop by itself.
    1. Makes the box's own ed25519 deploy key in <forge>\drop-key (Administrators, SYSTEM and the
       loop's account `quantgate` read only). The private key never leaves the box.
    2. Makes the drop clone folder <forge>\drop (quantgate may write it).
    3. Adds "drop" to <forge>\loop.json, keeping every other field as it is.
    4. Prints the PUBLIC key: register it on the drop repository as a READ-ONLY deploy key.
  Idempotent: a second run keeps the key and only rewrites the drop entry. Run as Administrator.
#>
param(
    [Parameter(Mandatory = $true)] [string] $DropUrl,   # git@gitlab.com:<owner>/quant-drop.git
    [string] $Branch = "main",
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $GateUser = "quantgate"
)
$ErrorActionPreference = "Stop"
if ($DropUrl -notmatch '^git@gitlab\.com:[A-Za-z0-9._/-]+\.git$') {
    throw "DropUrl must look like git@gitlab.com:<owner>/<repo>.git"
}
$Forge = Join-Path $Root "forge"
$cfgPath = Join-Path $Forge "loop.json"
if (-not (Test-Path -LiteralPath $cfgPath)) { throw "no ${cfgPath}: install the forge first" }

$keyDir = Join-Path $Forge "drop-key"
$checkout = Join-Path $Forge "drop"
$key = Join-Path $keyDir "drop_ed25519"
$null = New-Item -ItemType Directory -Force -Path $keyDir, $checkout
& icacls $keyDir /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "${GateUser}:(OI)(CI)M" | Out-Null
& icacls $checkout /grant "${GateUser}:(OI)(CI)M" | Out-Null

if (-not (Test-Path -LiteralPath $key)) {
    $kg = (Get-Command ssh-keygen -ErrorAction SilentlyContinue).Source
    if (-not $kg) { $kg = "C:\Program Files\Git\usr\bin\ssh-keygen.exe" }
    & $kg -q -t ed25519 -N '""' -C "quant-box-drop" -f $key
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $key)) { throw "ssh-keygen failed" }
}
# OpenSSH refuses a private key others can read: owner, SYSTEM, Administrators and the loop only.
& icacls $key /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" "${GateUser}:R" | Out-Null

$cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json
$drop = [pscustomobject]@{ url = $DropUrl; key = $key; checkout = $checkout; branch = $Branch }
if ($cfg.PSObject.Properties.Name -contains "drop") { $cfg.drop = $drop }
else { $cfg | Add-Member -NotePropertyName drop -NotePropertyValue $drop }
# The loop runs as $GateUser and reads loop.json through an EXPLICIT grant (the forge folder's own
# grant does not inherit). Move-Item of a fresh .part file replaced the file's ACL with the inherited
# one and dropped that grant: every QuantForge-Loop pass then died reading loop.json (box 11-26
# 04:07Z). So every explicit grant the old file had is re-granted after the write (icacls, no owner
# change), the loop's read grant is ensured, and checked.
$explicit = @((Get-Acl -LiteralPath $cfgPath).Access | Where-Object { -not $_.IsInherited -and $_.AccessControlType -eq 'Allow' })
$tmp = "$cfgPath.part"
$cfg | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $tmp -Encoding ascii
Move-Item -LiteralPath $tmp -Destination $cfgPath -Force
foreach ($r in $explicit) {
    $m = [Security.AccessControl.FileSystemRights]::Modify
    $perm = if (($r.FileSystemRights -band $m) -eq $m) { "M" } else { "R" }
    & icacls $cfgPath /grant "$($r.IdentityReference):($perm)" | Out-Null
}
& icacls $cfgPath /grant "${GateUser}:(R)" | Out-Null
$canRead = @((Get-Acl -LiteralPath $cfgPath).Access | Where-Object {
    "$($_.IdentityReference)" -match "(^|\\)$([regex]::Escape($GateUser))$" -and
    $_.AccessControlType -eq 'Allow' -and ($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::Read) })
if (-not $canRead) { throw "${GateUser} cannot read ${cfgPath} after the write: the loop would not start" }

Write-Output "DROP CONFIGURED url=$DropUrl branch=$Branch"
Write-Output ("PUBLIC KEY: " + (Get-Content -LiteralPath "$key.pub" -Raw).Trim())
