# FINAL_R25.ps1 -- zuck's own act (run elevated). TWO THINGS, both Audit-CLEARed:
#   A. Boot r25: the box guardian, phase 1 (read-only status for the r24 guard tasks).
#   B. One pipe's LIVE MERGE claude/live-merge-r25 at 34d751ad43, on zuck's own yes (2026-11-27
#      23:25Z: "Yes, land One pipe's LIVE merge 34d751ad43 with the gate, manifest and trust-set
#      changes"). It lands every Audit-CLEARed train since 11-10 on the live trading branch and
#      CHANGES THE MERGE GATE (.github/scripts/audit_gate.py), IMMUTABLE_MANIFEST.json,
#      release_identity and the trust set (TRUST_SET.json, protect.py, trust_check.py).
# It changes nothing it does not name below.
#
#   1. Checks the r25 bundle beside this file has exactly one head, db60dc05b6ab..., and is a
#      fast-forward of the running boot 4d61929c7d35....
#   2. Stages it for the box's own mover: the bundle, its .sha256 and Audit's verdict go into
#      C:\opt\bridge\quant\drop_local\forge_reboot (the mover still runs every one of its checks).
#   3. Writes the owner approval file for that exact commit (this act IS the owner's approval).
#   4. Only with -AllowClaudeStaging: grants the non-elevated Administrator user Modify on
#      drop_local\forge_reboot, so future Audit-cleared boots need no paste. The box's mover
#      still classifies every boot, runs the 10-minute veto on trust changes and requires an
#      owner file for the core. Residual: any program running as the non-elevated Administrator
#      could stage a boot there.
#   5. (B) Checks live-merge-r25.bundle beside this file has exactly one head, 34d751ad43..., and
#      that it and live-merge-r25.json carry their pinned sha256. Copies both into drop_local (the
#      forge opens the PR), then Audit's CLEAR verdict for that exact head, byte for byte, into
#      drop_local\verdicts (the forge merges it into LIVE on the Auditor's CLEAR).
# Nothing else: no task, no live position is touched, and no file is written directly into the
# live tree; the forge and the adopter do the rest under their own checks.
param([switch] $AllowClaudeStaging)
$ErrorActionPreference = 'Stop'
$Here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Head    = 'db60dc05b6abc1faaa8e036f829197bf638b5596'
$Base    = '4d61929c7d35a304ccdf6b6e235f3662d7cd82f5'
$Name    = 'boot-r25-db60dc05b'
$Verdict = '{"branch":"claude/boot-r25b","line":"AUDIT CLEAR db60dc05b6abc1faaa8e036f829197bf638b5596 merge"}'
$Bundle  = Join-Path $Here "$Name.bundle"
$RB      = 'C:\opt\bridge\quant\drop_local\forge_reboot'
$OA      = 'C:\ProgramData\QuantBox\forge\owner_approvals'
$Log     = 'C:\ProgramData\QuantBox\final_r25.log'
$DL      = 'C:\opt\bridge\quant\drop_local'
$LmHead  = '34d751ad438ae5659ee8a5cad57e04faf98e595d'
$LmBundleSha = 'faee219570173302c896b885a799a051cbe4d0947963e8931040423b07972d07'
$LmJsonSha   = 'ca9181ea9501c595c42d24a44ba073e4930616f556b253b63814fd906b0326b7'
$LmVerdict   = '{"branch":"claude/live-merge-r25","line":"AUDIT CLEAR 34d751ad438ae5659ee8a5cad57e04faf98e595d merge"}' + "`n"
$LmVerdictSha = '8625a6523739bc7dfe9082793ffe96d2d87e09d35c056faa0a38a5590e615461'
function Say([string] $m) { $l = "{0}  {1}" -f (Get-Date).ToUniversalTime().ToString('s'), $m; Add-Content -LiteralPath $Log -Value $l; $l }
function Stop-Here([string] $m) { Say "STOPPED: $m"; exit 1 }

$id = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $id.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Stop-Here 'not elevated: run as administrator' }
if ($Verdict -match 'PLACEHOLDER') { Stop-Here 'this copy carries no Audit verdict' }
if (-not (Test-Path -LiteralPath $Bundle)) { Stop-Here "no bundle at $Bundle" }
$G = @('-c', 'safe.directory=*', '-c', 'core.hooksPath=NUL', '-c', 'core.fsmonitor=false')
$heads = @(& git @G bundle list-heads $Bundle 2>$null | Where-Object { $_ -match '^[0-9a-f]{40} refs/heads/' })
if ($heads.Count -ne 1 -or -not $heads[0].StartsWith($Head)) { Stop-Here "bundle heads are not exactly $Head" }
$src = 'C:\ProgramData\QuantBox\forge\boot-src'
$boot = "$((Get-Content -Raw 'C:\ProgramData\QuantBox\forge\loop.json' | ConvertFrom-Json).boot)".Trim()
if ($boot -ne $Base) { Stop-Here "the running boot is $boot, not $Base" }
$tmp = Join-Path $env:TEMP ("r25chk_" + [guid]::NewGuid().ToString('N'))
& git @G clone -q --no-checkout $src $tmp
& git @G -C $tmp fetch -q $Bundle "+$(($heads[0] -split ' ')[1]):refs/heads/r25" 2>$null
& git @G -C $tmp merge-base --is-ancestor $Base $Head
$ff = $LASTEXITCODE
Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
if ($ff -ne 0) { Stop-Here "$Head is not a fast-forward of $Base" }
Say "bundle ok: one head $Head, fast-forward of $Base"

if (-not (Test-Path -LiteralPath $RB)) { $null = New-Item -ItemType Directory -Force -Path $RB }
Copy-Item -LiteralPath $Bundle -Destination (Join-Path $RB "$Name.bundle") -Force
$h = (Get-FileHash -LiteralPath (Join-Path $RB "$Name.bundle") -Algorithm SHA256).Hash.ToLower()
$U8 = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $RB "$Name.bundle.sha256"), "$h  $Name.bundle`n", $U8)
[IO.File]::WriteAllText((Join-Path $RB "$Name.verdict.json"), $Verdict, $U8)
Say "staged $Name (sha256 $h) and Audit's verdict in $RB"

if (-not (Test-Path -LiteralPath $OA -PathType Container)) { Stop-Here "no $OA (the mover's installer makes it)" }
[IO.File]::WriteAllText((Join-Path $OA "$Head.txt"), "zuck (owner) approves boot r25 ${Head}: box guardian phase 1, read-only status`n", $U8)
Say "owner approval written for $Head"

# ---- B. the LIVE merge (zuck's yes, 2026-11-27 23:25Z) ----
$LmB = Join-Path $Here 'live-merge-r25.bundle'
$LmJ = Join-Path $Here 'live-merge-r25.json'
foreach ($pair in @(@($LmB, $LmBundleSha), @($LmJ, $LmJsonSha))) {
    if (-not (Test-Path -LiteralPath $pair[0])) { Stop-Here "no $($pair[0])" }
    $x = (Get-FileHash -LiteralPath $pair[0] -Algorithm SHA256).Hash.ToLower()
    if ($x -ne $pair[1]) { Stop-Here "$($pair[0]) is sha256 $x, not $($pair[1])" }
}
$lmHeads = @(& git @G bundle list-heads $LmB 2>$null | Where-Object { $_ -match '^[0-9a-f]{40} refs/heads/' })
if ($lmHeads.Count -ne 1 -or $lmHeads[0] -ne "$LmHead refs/heads/claude/live-merge-r25") { Stop-Here "live-merge bundle heads are not exactly $LmHead" }
$vb = $U8.GetBytes($LmVerdict)
$sha = [Security.Cryptography.SHA256]::Create()
$vh = (($sha.ComputeHash($vb)) | ForEach-Object { $_.ToString('x2') }) -join ''
$sha.Dispose()
if ($vh -ne $LmVerdictSha) { Stop-Here "the LIVE merge verdict text is not sha256 $LmVerdictSha" }
Copy-Item -LiteralPath $LmB -Destination (Join-Path $DL 'live-merge-r25.bundle') -Force
Copy-Item -LiteralPath $LmJ -Destination (Join-Path $DL 'live-merge-r25.json') -Force
$DLV = Join-Path $DL 'verdicts'
if (-not (Test-Path -LiteralPath $DLV)) { $null = New-Item -ItemType Directory -Force -Path $DLV }
[IO.File]::WriteAllBytes((Join-Path $DLV 'live-merge-r25-34d751ad43.json'), $vb)
$wh = (Get-FileHash -LiteralPath (Join-Path $DLV 'live-merge-r25-34d751ad43.json') -Algorithm SHA256).Hash.ToLower()
if ($wh -ne $LmVerdictSha) { Stop-Here "the written LIVE merge verdict is $wh, not $LmVerdictSha" }
Say "LIVE merge ${LmHead}: packet and Audit's verdict staged in $DL"

if ($AllowClaudeStaging) {
    & icacls $RB /grant 'Administrator:(OI)(CI)M' | Out-Null
    if ($LASTEXITCODE) { Stop-Here 'could not grant staging on forge_reboot' }
    Say "future boots: the non-elevated Administrator may stage in $RB (the mover still gates every move)"
}
Say 'DONE: r25 staged and approved, LIVE merge staged with its verdict; the box takes both on its next pass'
'ALL DONE - nothing more is needed from you'
