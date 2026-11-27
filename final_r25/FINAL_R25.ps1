# FINAL_R25.ps1 -- zuck's own act (run elevated). Boot r25: the box guardian, phase 1 (read-only
# status for the r24 guard tasks). Audit-reviewed; it changes nothing it does not name below.
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
#   5. Copies Audit's CLEAR verdict for One pipe's LIVE merge, claude/live-merge-r25 at 34d751ad43,
#      byte for byte into drop_local\verdicts, so the forge lands that PR with no further act.
# Nothing else: no task, no trading file, no live position, no trust file is touched.
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
$LiveVerdictName = 'live-merge-r25-34d751ad43.json'
$LiveVerdict = '{"branch":"claude/live-merge-r25","line":"AUDIT CLEAR 34d751ad438ae5659ee8a5cad57e04faf98e595d merge"}' + "`n"
$DLV     = 'C:\opt\bridge\quant\drop_local\verdicts'
$LiveVerdictSha = '8625a6523739bc7dfe9082793ffe96d2d87e09d35c056faa0a38a5590e615461'
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

if (-not (Test-Path -LiteralPath $DLV)) { $null = New-Item -ItemType Directory -Force -Path $DLV }
$vb = $U8.GetBytes($LiveVerdict)
$vh = (([Security.Cryptography.SHA256]::Create().ComputeHash($vb)) | ForEach-Object { $_.ToString('x2') }) -join ''
if ($vh -ne $LiveVerdictSha) { Stop-Here "the LIVE merge verdict text is not sha256 $LiveVerdictSha" }
[IO.File]::WriteAllBytes((Join-Path $DLV $LiveVerdictName), $vb)
$wh = (Get-FileHash -LiteralPath (Join-Path $DLV $LiveVerdictName) -Algorithm SHA256).Hash.ToLower()
if ($wh -ne $LiveVerdictSha) { Stop-Here "the written LIVE merge verdict is $wh, not $LiveVerdictSha" }
Say "Audit's verdict for claude/live-merge-r25 34d751ad43 copied to $DLV"

if ($AllowClaudeStaging) {
    & icacls $RB /grant 'Administrator:(OI)(CI)M' | Out-Null
    if ($LASTEXITCODE) { Stop-Here 'could not grant staging on forge_reboot' }
    Say "future boots: the non-elevated Administrator may stage in $RB (the mover still gates every move)"
}
Say 'DONE: r25 staged and approved, LIVE merge verdict delivered; the box takes both on its next pass'
'ALL DONE - nothing more is needed from you'
