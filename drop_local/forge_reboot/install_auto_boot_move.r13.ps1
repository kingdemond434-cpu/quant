# ONE-TIME INSTALL of boot mover r18c (installer r13; zuck 2026-11-26 22:25Z "make it so silence is my word",
# 22:59Z "make it 10 minutes all these"; 2026-11-27 01:16-01:21Z "as soon as builds complete they go live").
# Run ONCE from an elevated PowerShell, as zuck's own act:
#   .\install_auto_boot_move.r13.ps1 -ExpectSha256 <Audit-CLEAR sha256 of auto_boot_move.r18c.ps1>
# It does exactly two things:
#  1. Installs drop_local\forge_reboot\auto_boot_move.r18c.ps1 as the mover, only if its sha256 is the Audit-CLEAR
#     one and it parses with 0 errors (as r11 did). The old mover is kept beside it as evidence.
#  2. Re-registers QuantForge-BootMove every 5 min (was 15), same SYSTEM principal, IgnoreNew, 1 h limit.
# It KEEPS owner_approvals as it is (re-proves it admin-only and refuses if not), writes NO approval, touches no
# boot, no trust folder, no token, no other task. Reversal: re-run installer r11 with the r18b sha256.
param([Parameter(Mandatory = $true)][string] $ExpectSha256)
$ErrorActionPreference = 'Stop'
$F = 'C:\ProgramData\QuantBox\forge'
$Local = 'C:\opt\bridge\quant\drop_local'
$SrcFile = Join-Path $Local 'forge_reboot\auto_boot_move.r18c.ps1'
$Dst = "$F\auto_boot_move.ps1"
$Task = 'QuantForge-BootMove'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not ([Security.Principal.WindowsPrincipal]::new($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'not elevated: right-click PowerShell, Run as administrator'
}
$OA = "$F\owner_approvals"
if (-not (Test-Path -LiteralPath $OA -PathType Container)) { throw "$OA is missing (installer r11 makes it); nothing installed" }
if ((Get-Item -LiteralPath $OA -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "$OA is a reparse point; nothing installed" }
$acl = Get-Acl -LiteralPath $OA
$bad = @($acl.Access | Where-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin @('S-1-5-32-544', 'S-1-5-18') -or $_.IsInherited })
if ($bad.Count) { throw "$OA is not admin-only ($($bad.Count) other entries); nothing installed" }
if (-not (Test-Path -LiteralPath $SrcFile)) { throw "$SrcFile is missing; nothing installed" }
$tmp = "$Dst.new"
Copy-Item -LiteralPath $SrcFile -Destination $tmp -Force
$got = (Get-FileHash -Algorithm SHA256 -LiteralPath $tmp).Hash
if ($got -ne $ExpectSha256.ToUpper()) { Remove-Item -LiteralPath $tmp -Force; throw "sha256 $got is not the Audit-CLEAR $ExpectSha256; nothing installed" }
$perr = $null; [void][System.Management.Automation.Language.Parser]::ParseFile($tmp, [ref]$null, [ref]$perr)
if ($perr -and $perr.Count) { Remove-Item -LiteralPath $tmp -Force; throw ("parse errors in the candidate mover ({0}); nothing installed" -f $perr.Count) }
Write-Host 'PARSE OK: 0 errors'
if (Test-Path -LiteralPath $Dst) {
    Copy-Item -LiteralPath $Dst -Destination ("$F\auto_boot_move.pre-r18c.{0:yyyyMMddTHHmmssZ}.ps1" -f (Get-Date).ToUniversalTime())
}
Move-Item -LiteralPath $tmp -Destination $Dst -Force
& "$env:SystemRoot\System32\icacls.exe" $Dst /inheritance:r /grant:r '*S-1-5-32-544:F' '*S-1-5-18:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw "icacls $Dst exited $LASTEXITCODE" }
$act = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Dst`"" -WorkingDirectory $F
$trg = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1) -StartWhenAvailable
$pri = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $Task -Action $act -Trigger $trg -Settings $set -Principal $pri -Force | Out-Null
$t = Get-ScheduledTask -TaskName $Task
Write-Host ("INSTALLED r18c: {0} sha256 {1}; task {2} state {3}, every 5 min as SYSTEM" -f $Dst, $got, $Task, $t.State)
Write-Host 'r13 DONE'
