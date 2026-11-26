# ONE-TIME INSTALL of boot mover r18 + the trust shrink (installer r10; zuck 2026-11-26 17:33Z "cut every protected
# change possible all except core"). Run ONCE as admin, as zuck's own act:
#   .\install_auto_boot_move.r10.ps1 -ExpectSha256 <r18 sha256> -ApproveBoot <boot r17 sha>
# 1. Installs C:\opt\bridge\quant\drop_local\forge_reboot\auto_boot_move.r18.ps1 as the mover, only if its sha256 is the
#    Audit-CLEAR one and it parses with 0 errors.
# 2. Creates $F\owner_approvals fresh (owner Administrators, inheritance removed, Admins/SYSTEM only; a pre-existing
#    one is kept aside as evidence). r18 reads owner approvals ONLY there, never from the drop.
# 3. Seeds boot r17 (Audit CLEAR) into the drop checkout's forge_reboot and, with -ApproveBoot equal to that exact sha,
#    writes owner_approvals\<sha>.txt: zuck running this line IS his approval of r17 (it changes the checker and
#    TRUST_SET, which only the owner may approve). r17 descends from r16, so it carries r16 too.
param([Parameter(Mandatory = $true)][string] $ExpectSha256, [Parameter(Mandatory = $true)][string] $ApproveBoot)
$ErrorActionPreference = 'Stop'
$F = 'C:\ProgramData\QuantBox\forge'
$Cfg = Get-Content -Raw "$F\loop.json" | ConvertFrom-Json
$Local = 'C:\opt\bridge\quant\drop_local'   # (r9) GitLab is gone: the mover comes from the local drop folder
$SrcFile = Join-Path $Local 'forge_reboot\auto_boot_move.r18.ps1'
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
$GuardDir = "$F\guard"   # (r4 installer, Audit MF 12:58Z) the guardian copy's home: fresh, owner Administrators, Admins/SYSTEM only
if (Test-Path -LiteralPath $GuardDir) {   # never adopt a pre-existing one (Users can create dirs in $F): kept as evidence
    Move-Item -LiteralPath $GuardDir -Destination ("$F\guard.preinstall.{0:yyyyMMddTHHmmssZ}" -f (Get-Date).ToUniversalTime())
}
New-Item -ItemType Directory -Path $GuardDir | Out-Null
& "$env:SystemRoot\System32\icacls.exe" $GuardDir /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls setowner $GuardDir exited $LASTEXITCODE" }
& "$env:SystemRoot\System32\icacls.exe" $GuardDir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls $GuardDir exited $LASTEXITCODE" }
$OA = "$F\owner_approvals"   # (r10, Audit r18 MF1) owner approvals: outside the drop, fresh, admin-only
if (Test-Path -LiteralPath $OA) {
    Move-Item -LiteralPath $OA -Destination ("$F\owner_approvals.preinstall.{0:yyyyMMddTHHmmssZ}" -f (Get-Date).ToUniversalTime())
}
New-Item -ItemType Directory -Path $OA | Out-Null
& "$env:SystemRoot\System32\icacls.exe" $OA /setowner '*S-1-5-32-544' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls setowner $OA exited $LASTEXITCODE" }
& "$env:SystemRoot\System32\icacls.exe" $OA /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls $OA exited $LASTEXITCODE" }
$act = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Dst`"" -WorkingDirectory $F
$trg = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(2)) -RepetitionInterval (New-TimeSpan -Minutes 15)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1) -StartWhenAvailable
$pri = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $Task -Action $act -Trigger $trg -Settings $set -Principal $pri -Force | Out-Null
$t = Get-ScheduledTask -TaskName $Task
Write-Host ("INSTALLED: {0} sha256 {1}; task {2} state {3}, every 15 min as SYSTEM; journal {4}" -f $Dst, $got, $Task, $t.State, $Journal)
# (r10) Seed boot r17 (Audit CLEAR) byte for byte from drop_local\owner_seed (a folder drop_pull never stages, so r17 cannot reach the r17 mover and freeze r16 before this runs); the mover applies every one of its own checks.
$R17 = '7fc7dab7cf07875d945ed70e49ef27a5099fd38b'
$R17N = 'boot-r17-7fc7dab7c'
$R17BUNDLE = '116CA289F07F4EB712F21251E72DB5D8A08676CC6A5AAB81DFCD4248C837E394'
if ($ApproveBoot -ne $R17) { throw "-ApproveBoot $ApproveBoot is not boot r17 $R17; mover installed, nothing approved" }
$RB = Join-Path $Cfg.drop.checkout 'forge_reboot'
foreach ($n in "$R17N.bundle", "$R17N.bundle.sha256", "$R17N.verdict.json") {
    $from = Join-Path $Local "owner_seed\$n"
    if (-not (Test-Path -LiteralPath $from)) { throw "$from is missing; mover installed, boot r17 not seeded" }
    Copy-Item -LiteralPath $from -Destination (Join-Path $RB $n) -Force
}
$have = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $RB "$R17N.bundle")).Hash
if ($have -ne $R17BUNDLE.ToUpper()) { throw "boot r17 bundle sha256 $have is not the Audit-CLEAR one; nothing approved" }
[IO.File]::WriteAllText((Join-Path $OA "$R17.txt"), "zuck approves boot r17 $R17 (installer r10, run by the owner)`n", [Text.UTF8Encoding]::new($false))
Write-Host "SEEDED and APPROVED: boot r17 $R17 in $RB; owner approval in $OA. The mover moves to it on its next run."
& "$env:SystemRoot\System32\icacls.exe" $OA
