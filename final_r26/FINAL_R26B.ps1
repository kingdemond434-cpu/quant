# FINAL_R26B.ps1 -- zuck's own act (run elevated). THREE PARTS, in this fixed order. If any
# check fails, it stops before every later part. Every part was cleared by the Audit thread at
# the exact sha named here.
#
#   A. UNFREEZE THE FORGE LOOP. Since 2026-11-27 18:29Z the QuantForge-Loop task (account
#      quantgate) dies every pass: it cannot list C:\opt\bridge\quant\packets_inbox (that folder
#      grants only Administrator, SYSTEM and Administrators), so nothing has been delivered since.
#      The fix is one command,
#          icacls C:\opt\bridge\quant\packets_inbox /grant quantgate:(OI)(CI)(RX)
#      which is read and list only, for that folder only. A post-check confirms the entry.
#      (Audit 2026-11-28 00:00Z: "explicit icacls ... with a post-check, touching no other
#      folder".)
#   B. One pipe's LIVE MERGE claude/live-merge-r25 at 34d751ad438ae5659ee8a5cad57e04faf98e595d.
#      This is on zuck's own yes (2026-11-27 23:25:45Z: "Yes, land One pipe's LIVE merge
#      34d751ad43 with the gate, manifest and trust-set changes").
#      - It lands every Audit-cleared train since 11-10 on the live trading branch.
#      - It CHANGES THE MERGE GATE (.github/scripts/audit_gate.py), IMMUTABLE_MANIFEST.json,
#        release_identity and the trust set (TRUST_SET.json, protect.py, trust_check.py).
#      - The packet goes into drop_local, where the forge opens the PR. Audit's CLEAR verdict
#        file is copied byte for byte into drop_local\verdicts, where the forge merges on the
#        Auditor's CLEAR.
#   C. Boot r25d at 923f0184217e3fd76822c4a55658cda2e4f7dfb8. Its parents are r25c.1 bfac69dfd
#      and r25 db60dc05b, so the bundle carries the box guardian phases 1 and 3 and the r25d fix.
#      - r25d stops an unreadable packets inbox from ever killing the loop again.
#      - It is staged for the box's own mover in drop_local\forge_reboot, which still runs every
#        one of its checks.
#      - It also writes the owner approval file for that exact commit. This act IS the owner's
#        approval.
#   (Boot r26 is NOT in this act. It changes the box's merge rules and adds the reviewer and
#   signer code, so it waits for zuck's own separate yes.)
#
# HOW THE ADMIN WINDOW CAN VERIFY BEFORE RUNNING
#   - Every input is pinned below by sha256, and the script refuses on any mismatch.
#       live-merge-r25.bundle    faee219570173302c896b885a799a051cbe4d0947963e8931040423b07972d07
#                                (one head 34d751ad43...)
#       live-merge-r25.json      ca9181ea9501c595c42d24a44ba073e4930616f556b253b63814fd906b0326b7
#       live-merge-r25-34d751ad43.verdict.json
#                                8625a6523739bc7dfe9082793ffe96d2d87e09d35c056faa0a38a5590e615461
#       boot-r25d-923f01842.bundle
#                                57bab139ff43cee9b9bd6d010d03a7a9c195f3b8dbc714bcbc485cb15319380c
#                                (one head 923f01842...)
#       boot-r25d-923f01842.verdict.json
#                                a2c1f9403f76707c57d0a1098d65a66bc96d2592b0ff790957390684d1b8022b
#   - The three verdict files are Audit's own files, copied unchanged. This script does not write
#     a verdict.
#       live-merge-r25-34d751ad43.verdict.json reads
#         {"branch":"claude/live-merge-r25","line":"AUDIT CLEAR 34d751ad438ae5659ee8a5cad57e04faf98e595d merge"}
#       boot-r25d-923f01842.verdict.json reads
#         {"branch":"claude/boot-r25d","line":"AUDIT CLEAR 923f0184217e3fd76822c4a55658cda2e4f7dfb8 merge"}
#   - Provenance: Audit's notes are autonomy/LIVE_MERGE_R25_9663b93706_AUDIT.md (and its
#     follow-ups), autonomy/R26_DESIGN.md ("Audit 2026-11-28 00:00Z") and the BOOT_R26 audit note
#     in the project files.
#
# It changes nothing it does not name above. It touches no task, no live position and no file in
# the live tree. The forge and the adopter do the rest under their own checks. It takes no
# switches.
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Log  = 'C:\ProgramData\QuantBox\final_r26b.log'
$PI   = 'C:\opt\bridge\quant\packets_inbox'
$DL   = 'C:\opt\bridge\quant\drop_local'
$RB   = Join-Path $DL 'forge_reboot'
$OA   = 'C:\ProgramData\QuantBox\forge\owner_approvals'
$Forge = 'C:\ProgramData\QuantBox\forge'
$LmHead = '34d751ad438ae5659ee8a5cad57e04faf98e595d'
$Boots = @(
    @{ head = '923f0184217e3fd76822c4a55658cda2e4f7dfb8'; name = 'boot-r25d-923f01842'; ref = 'refs/heads/claude/boot-r25d'
       why = 'boot r25d: an unreadable packets inbox never stops the forge pass' }
)
$Pins = [ordered]@{
    'live-merge-r25.bundle'                  = 'faee219570173302c896b885a799a051cbe4d0947963e8931040423b07972d07'
    'live-merge-r25.json'                    = 'ca9181ea9501c595c42d24a44ba073e4930616f556b253b63814fd906b0326b7'
    'live-merge-r25-34d751ad43.verdict.json' = '8625a6523739bc7dfe9082793ffe96d2d87e09d35c056faa0a38a5590e615461'
    'boot-r25d-923f01842.bundle'             = '57bab139ff43cee9b9bd6d010d03a7a9c195f3b8dbc714bcbc485cb15319380c'
    'boot-r25d-923f01842.verdict.json'       = 'a2c1f9403f76707c57d0a1098d65a66bc96d2592b0ff790957390684d1b8022b'
}
$U8 = New-Object Text.UTF8Encoding($false)
$G  = @('-c', 'safe.directory=*', '-c', 'core.hooksPath=NUL', '-c', 'core.fsmonitor=false')
function Say([string] $m) { $l = '{0}  {1}' -f (Get-Date).ToUniversalTime().ToString('s'), $m; Add-Content -LiteralPath $Log -Value $l; $l }
function Stop-Here([string] $m) { Say "STOPPED: $m"; exit 1 }
function Get-Sha([string] $p) { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower() }
function Get-OneHead([string] $bundle) {
    $h = @(& git @G bundle list-heads $bundle 2>$null | Where-Object { $_ -match '^[0-9a-f]{40} refs/heads/' })
    if ($h.Count -ne 1) { return $null }
    return $h[0]
}

# ---- 0. every input, before anything changes ----
$id = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $id.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Stop-Here 'not elevated: run as administrator' }
foreach ($k in $Pins.Keys) {
    $p = Join-Path $Here $k
    if (-not (Test-Path -LiteralPath $p)) { Stop-Here "missing $p" }
    $x = Get-Sha $p
    if ($x -ne $Pins[$k]) { Stop-Here "$k is sha256 $x, not $($Pins[$k])" }
}
if ((Get-OneHead (Join-Path $Here 'live-merge-r25.bundle')) -ne "$LmHead refs/heads/claude/live-merge-r25") { Stop-Here "the live-merge bundle's one head is not $LmHead" }
foreach ($b in $Boots) {
    if ((Get-OneHead (Join-Path $Here "$($b.name).bundle")) -ne "$($b.head) $($b.ref)") { Stop-Here "the $($b.name) bundle's one head is not $($b.head)" }
}
foreach ($d in @($PI, $DL, $RB, $OA)) { if (-not (Test-Path -LiteralPath $d -PathType Container)) { Stop-Here "no folder $d" } }
try { $gateSid = (New-Object Security.Principal.NTAccount('quantgate')).Translate([Security.Principal.SecurityIdentifier]).Value }
catch { Stop-Here 'the quantgate account does not exist' }
Say 'inputs ok: seven files match their pinned sha256, every bundle carries exactly its one head'

# ---- A. packets_inbox: quantgate may read and list it ----
& icacls $PI /grant 'quantgate:(OI)(CI)(RX)' | Out-Null
if ($LASTEXITCODE) { Stop-Here "icacls on $PI failed ($LASTEXITCODE)" }
$rx = [int][Security.AccessControl.FileSystemRights]::ReadAndExecute
$ok = $false
foreach ($r in (Get-Acl -LiteralPath $PI).Access) {
    if ("$($r.AccessControlType)" -ne 'Allow') { continue }
    if ($r.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -ne $gateSid) { continue }
    $inh = "$($r.InheritanceFlags)"
    if ((([int]$r.FileSystemRights) -band $rx) -eq $rx -and $inh -match 'ContainerInherit' -and $inh -match 'ObjectInherit') { $ok = $true }
}
if (-not $ok) { Stop-Here "post-check: no inheritable read+list entry for quantgate on $PI" }
Say "A done: quantgate may read and list $PI (post-checked); no other folder touched"

# ---- B. the LIVE merge (zuck's yes, 2026-11-27 23:25:45Z) ----
Copy-Item -LiteralPath (Join-Path $Here 'live-merge-r25.bundle') -Destination (Join-Path $DL 'live-merge-r25.bundle') -Force
Copy-Item -LiteralPath (Join-Path $Here 'live-merge-r25.json') -Destination (Join-Path $DL 'live-merge-r25.json') -Force
$DLV = Join-Path $DL 'verdicts'
if (-not (Test-Path -LiteralPath $DLV)) { $null = New-Item -ItemType Directory -Force -Path $DLV }
$lv = Join-Path $DLV 'live-merge-r25-34d751ad43.json'
[IO.File]::WriteAllBytes($lv, [IO.File]::ReadAllBytes((Join-Path $Here 'live-merge-r25-34d751ad43.verdict.json')))
foreach ($pair in @(@((Join-Path $DL 'live-merge-r25.bundle'), 'live-merge-r25.bundle'), @((Join-Path $DL 'live-merge-r25.json'), 'live-merge-r25.json'),
                    @($lv, 'live-merge-r25-34d751ad43.verdict.json'))) {
    if ((Get-Sha $pair[0]) -ne $Pins[$pair[1]]) { Stop-Here "post-check: $($pair[0]) is not the pinned bytes" }
}
Say "B done: LIVE merge $LmHead packet and Audit's CLEAR staged in $DL (post-checked)"

# ---- C. boot r25d, for the box's mover ----
$boot = "$((Get-Content -Raw -LiteralPath (Join-Path $Forge 'loop.json') | ConvertFrom-Json).boot)".Trim()
if ($boot -notmatch '^[0-9a-f]{40}$') { Stop-Here 'cannot read the running boot from loop.json' }
foreach ($b in $Boots) {
    $tmp = Join-Path $env:TEMP ('bootchk_' + [guid]::NewGuid().ToString('N'))
    & git @G clone -q --no-checkout (Join-Path $Forge 'boot-src') $tmp
    & git @G -C $tmp fetch -q (Join-Path $Here "$($b.name).bundle") "+$($b.ref):refs/heads/chk" 2>$null
    & git @G -C $tmp merge-base --is-ancestor $boot $b.head
    $ff = $LASTEXITCODE
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
    if ($ff -ne 0) { Stop-Here "$($b.head) is not a fast-forward of the running boot $boot" }
    $dest = Join-Path $RB "$($b.name).bundle"
    Copy-Item -LiteralPath (Join-Path $Here "$($b.name).bundle") -Destination $dest -Force
    $h = Get-Sha $dest
    if ($h -ne $Pins["$($b.name).bundle"]) { Stop-Here "post-check: the staged $($b.name) bundle is $h" }
    [IO.File]::WriteAllText((Join-Path $RB "$($b.name).bundle.sha256"), "$h  $($b.name).bundle`n", $U8)
    $vd = Join-Path $RB "$($b.name).verdict.json"
    [IO.File]::WriteAllBytes($vd, [IO.File]::ReadAllBytes((Join-Path $Here "$($b.name).verdict.json")))
    if ((Get-Sha $vd) -ne $Pins["$($b.name).verdict.json"]) { Stop-Here "post-check: the staged $($b.name) verdict is not Audit's bytes" }
    [IO.File]::WriteAllText((Join-Path $OA "$($b.head).txt"), "zuck (owner) approves $($b.why) ($($b.head))`n", $U8)
    Say "staged $($b.name) $($b.head) (fast-forward of $boot) with Audit's CLEAR and the owner approval"
}

Say 'DONE: the loop can read its inbox again; the LIVE merge and r25d are staged; the box takes them on its next pass'
'ALL DONE - nothing more is needed from you'
