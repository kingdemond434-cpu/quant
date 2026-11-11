# INSTALL THE ROOT RE-PIN SERVICE (SEALED; NO_OWNER_EVER). The last box step of the final sitting.
#
# Run ONCE, in an Administrator PowerShell on the box, after the ROOT-path PR is merged AND the
# box has adopted it (C:\opt\quant contains ops\release\authority\repin.py):
#     powershell -ExecutionPolicy Bypass -File C:\opt\quant\ops\release\authority\install_repin.ps1
#
# It copies repin.py and root_path.py from the ADOPTED live tree into C:\opt\authority\sealed,
# which only Administrators and SYSTEM may write (Users read), and registers the task
# Quant-RootRepin to run that sealed copy as SYSTEM every 5 minutes. The copy that runs never
# changes after this: a later PR to repin.py or root_path.py is SEALED CORE and needs zuck, and
# installing it again is zuck's own act. The service re-pins only a released, adopted tree after
# a ROOT-path merge it re-verifies (repin.py); anything else pins nothing and alerts.
[CmdletBinding()]
param(
    [string] $LiveTree = "C:\opt\quant",
    [string] $Registry = "C:\opt\audit_registry",
    [string] $AuthHome = "C:\opt\authority",
    [string] $Notify = ""
)
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
$Src = Join-Path $LiveTree "ops\release\authority"
foreach ($f in @("repin.py", "root_path.py")) {
    if (-not (Test-Path -LiteralPath (Join-Path $Src $f))) { throw "$f is not in the adopted tree $LiveTree yet: adopt the ROOT-path merge first." }
}
if (-not (Test-Path -LiteralPath (Join-Path $Registry "ROOT_PIN.json"))) { throw "no ROOT_PIN.json in ${Registry}: run the bootstrap first." }
$Python = (Get-Content -Raw (Join-Path $AuthHome "config.json") | ConvertFrom-Json).python
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw "no python in $AuthHome\config.json" }
if (-not $Notify) { $Notify = [Environment]::GetEnvironmentVariable("QUANT_REGISTRY_NOTIFY", "Machine") }

$Sealed = Join-Path $AuthHome "sealed"
New-Item -ItemType Directory -Force -Path $Sealed | Out-Null
& icacls $Sealed /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Users:(OI)(CI)RX" | Out-Null
foreach ($f in @("repin.py", "root_path.py")) { Copy-Item -Force -LiteralPath (Join-Path $Src $f) -Destination (Join-Path $Sealed $f) }
$hashes = foreach ($f in @("repin.py", "root_path.py")) { "{0} {1}" -f (Get-FileHash -Algorithm SHA256 (Join-Path $Sealed $f)).Hash.ToLower(), $f }
$hashes | Set-Content -LiteralPath (Join-Path $Sealed "INSTALLED.sha256") -Encoding ASCII

# a dry check before the task exists: it must run and judge (no ROOT merge in flight -> CLEAR)
$args_ = @("-I", (Join-Path $Sealed "repin.py"), "--registry", $Registry, "--live-tree", $LiveTree)
if ($Notify) { $args_ += @("--notify", $Notify) }
& $Python @args_
if ($LASTEXITCODE -ne 0) { throw "repin.py did not run cleanly (rc $LASTEXITCODE): the task was NOT registered." }

$quoted = ($args_ | ForEach-Object { if ($_ -match '\s') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
$act = New-ScheduledTaskAction -Execute $Python -Argument $quoted -WorkingDirectory $Sealed
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew -StartWhenAvailable
$prn = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "Quant-RootRepin" -Action $act -Trigger $trg -Settings $set -Principal $prn -Force | Out-Null
Write-Host "DONE: Quant-RootRepin runs $Sealed\repin.py as SYSTEM every 5 min." -ForegroundColor Green
$hashes | Out-Host
if (-not $Notify) { Write-Host "NOTE: no notify command found; re-pins and refusals are logged to $Registry\repin.log.jsonl only." -ForegroundColor Yellow }
