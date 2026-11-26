# ONE-TIME INSTALL of the automatic boot move (zuck 2026-11-26 12:38Z "Remove that safety room ... Root").
# Run ONCE as admin (zuck's box Bypass session). After this, boot moves need nobody: QuantForge-BootMove (SYSTEM,
# every 15 min) runs C:\ProgramData\QuantBox\forge\auto_boot_move.ps1, which moves the boot only to an Audit-CLEAR,
# sha256-verified, fast-forward drop bundle that touches no trust-set path (see that script's header).
# The installed copy is admin/SYSTEM-only: the drop, quantgate and quantci cannot change it. Changing the mover itself
# is a ROOT change (Audit CLEAR + zuck's 1 h silent veto + an admin run of this installer with the new sha).
# (r9) Source: C:\opt\bridge\quant\drop_local (no GitLab). Also seeds boot r13 (local drop) for the mover.
# (r8) Mover r17 (PQ4, Audit CLEAR 0e8a4668 15:47Z): refuses unless the blob's sha256 is the expected one AND it parses
# with 0 errors. Run as: .\install_auto_boot_move.ps1 -ExpectSha256 0e8a46687593a6f6f81dd9633cdfecc510e7b3457de18503ed321817ed373d0e
# Idempotent: re-running with the same file changes nothing but re-asserts the ACL and task.
param([Parameter(Mandatory = $true)][string] $ExpectSha256)
$ErrorActionPreference = 'Stop'
$F = 'C:\ProgramData\QuantBox\forge'
$Cfg = Get-Content -Raw "$F\loop.json" | ConvertFrom-Json
$Local = 'C:\opt\bridge\quant\drop_local'   # (r9) GitLab is gone: the mover comes from the local drop folder
$SrcFile = Join-Path $Local 'forge_reboot\auto_boot_move.r17.ps1'
$Dst = "$F\auto_boot_move.ps1"
$Journal = "$F\boot_moves.jsonl"
$Task = 'QuantForge-BootMove'
function Set-AdminOnly([string] $p) {
    & "$env:SystemRoot\System32\icacls.exe" $p /inheritance:r /grant:r '*S-1-5-32-544:F' '*S-1-5-18:F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls $p exited $LASTEXITCODE" }
}
# (r9) Byte copy of the local file (written by the Autonomy seat with folder access; no git, no line-ending change).
$tmp = "$Dst.new"
if (-not (Test-Path -LiteralPath $SrcFile)) { throw "$SrcFile is missing; nothing installed" }
Copy-Item -LiteralPath $SrcFile -Destination $tmp -Force
$got = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash
if ($got -ne $ExpectSha256.ToUpper()) { Remove-Item -LiteralPath $tmp -Force; throw "sha256 $got is not the Audit-CLEAR $ExpectSha256; nothing installed" }
# (r8, Audit 15:47Z) the exact file must parse with 0 errors before it replaces the running mover
$perr = $null; [void][System.Management.Automation.Language.Parser]::ParseFile($tmp, [ref]$null, [ref]$perr)
if ($perr -and $perr.Count) { Remove-Item -LiteralPath $tmp -Force; throw ("parse errors in the candidate mover ({0}): {1}; nothing installed" -f $perr.Count, (($perr | Select-Object -First 3 | ForEach-Object { $_.Message }) -join ' | ')) }
Write-Host 'PARSE OK: 0 errors'
Move-Item -LiteralPath $tmp -Destination $Dst -Force
Set-AdminOnly $Dst
if (-not (Test-Path -LiteralPath $Journal)) { New-Item -ItemType File -Path $Journal | Out-Null }
Set-AdminOnly $Journal
$Ledger = "$F\veto_ledger.jsonl"   # (r4) the 1 h silent-veto ledger: created here, admin/SYSTEM-only, owner Administrators
if (Test-Path -LiteralPath $Ledger) {   # (r3, Audit MF1) never adopt a pre-existing ledger: kept as evidence, replaced by a fresh one
    Move-Item -LiteralPath $Ledger -Destination ("$F\veto_ledger.preinstall.{0:yyyyMMddTHHmmssZ}.jsonl" -f (Get-Date).ToUniversalTime())
}
New-Item -ItemType File -Path $Ledger | Out-Null
& "$env:SystemRoot\System32\icacls.exe" $Ledger /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls setowner $Ledger exited $LASTEXITCODE" }
Set-AdminOnly $Ledger
$GuardDir = "$F\guard"   # (r4 installer, Audit MF 12:58Z) the guardian copy's home: fresh, owner Administrators, Admins/SYSTEM only
if (Test-Path -LiteralPath $GuardDir) {   # never adopt a pre-existing one (Users can create dirs in $F): kept as evidence
    Move-Item -LiteralPath $GuardDir -Destination ("$F\guard.preinstall.{0:yyyyMMddTHHmmssZ}" -f (Get-Date).ToUniversalTime())
}
New-Item -ItemType Directory -Path $GuardDir | Out-Null
& "$env:SystemRoot\System32\icacls.exe" $GuardDir /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls setowner $GuardDir exited $LASTEXITCODE" }
& "$env:SystemRoot\System32\icacls.exe" $GuardDir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls $GuardDir exited $LASTEXITCODE" }
$act = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Dst`"" -WorkingDirectory $F
$trg = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(2)) -RepetitionInterval (New-TimeSpan -Minutes 15)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1) -StartWhenAvailable
$pri = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $Task -Action $act -Trigger $trg -Settings $set -Principal $pri -Force | Out-Null
$t = Get-ScheduledTask -TaskName $Task
Write-Host ("INSTALLED: {0} sha256 {1}; task {2} state {3}, every 15 min as SYSTEM; journal {4}" -f $Dst, $got, $Task, $t.State, $Journal)
# (r9) Seed the first boot packet that teaches the box the local drop (boot r13, Audit CLEAR 1a7953985): its three files
# are copied byte for byte from the local drop into the drop checkout's forge_reboot, where the mover reads them and
# applies every one of its own checks. Nothing else is copied.
$RB = Join-Path $Cfg.drop.checkout 'forge_reboot'
foreach ($n in 'boot-r13-1a7953985.bundle', 'boot-r13-1a7953985.bundle.sha256', 'boot-r13-1a7953985.verdict.json') {
    $from = Join-Path $Local "forge_reboot\$n"
    if (-not (Test-Path -LiteralPath $from)) { throw "$from is missing; mover installed, boot r13 not seeded" }
    Copy-Item -LiteralPath $from -Destination (Join-Path $RB $n) -Force
}
$want = ((Get-Content -Raw -LiteralPath (Join-Path $RB 'boot-r13-1a7953985.bundle.sha256')) -split '\s+')[0].ToUpper()
$have = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $RB 'boot-r13-1a7953985.bundle')).Hash
if ($have -ne $want -or $have -ne 'CEC8A4B8C5BB59599732CAD1899A8EA283D84EC97E28C1981AEE4C1070503707') { throw "boot r13 bundle sha256 $have is not cec8a4b8...; the mover will refuse it" }
Write-Host "SEEDED: boot r13 1a7953985 in $RB (sha256 verified); the mover moves to it on its next eligible run"
& "$env:SystemRoot\System32\icacls.exe" $Dst
