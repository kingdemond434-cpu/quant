# INSTALL THE ROOT RE-PIN SERVICE (SEALED; NO_OWNER_EVER). The last box step of the final sitting.
#
# Run ONCE, in an Administrator PowerShell on the box, after the ROOT-path PR is merged AND the
# box has adopted it (C:\opt\quant contains ops\release\authority\repin.py):
#     powershell -ExecutionPolicy Bypass -File C:\opt\quant\ops\release\authority\install_repin.ps1
#
# It copies repin.py, root_path.py, notify.py and ROOT_POLICY.json (and freezes a copy of
# libs\ops\alert_channels.py for the sealed notifier) from the ADOPTED live tree into C:\opt\authority\sealed,
# which only Administrators and SYSTEM may write (Users read), and registers the task
# Quant-RootRepin to run that sealed copy as SYSTEM every 5 minutes. The copy that runs never
# changes after this: a later PR to any of them is SEALED CORE and needs zuck, and installing it
# again is zuck's own act (the authority keeps the ROOT path off while the installed files differ
# from LIVE's). The service sends the ROOT veto notices the authority requests and re-pins only a
# released, adopted tree after a ROOT-path merge it re-verifies (repin.py); anything else pins
# nothing and alerts. Nothing it runs comes from the live tree.
[CmdletBinding()]
param(
    [string] $LiveTree = "C:\opt\quant",
    [string] $Registry = "C:\opt\audit_registry",
    [string] $AuthHome = "C:\opt\authority"
)
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Open PowerShell with 'Run as administrator' and run this again."
}
$Src = Join-Path $LiveTree "ops\release\authority"
$Files = @("repin.py", "root_path.py", "notify.py", "ROOT_POLICY.json")
foreach ($f in $Files) {
    if (-not (Test-Path -LiteralPath (Join-Path $Src $f))) { throw "$f is not in the adopted tree $LiveTree yet: adopt the ROOT-path merge first." }
}
$Channels = Join-Path $LiveTree "libs\ops\alert_channels.py"
if (-not (Test-Path -LiteralPath $Channels)) { throw "no libs\ops\alert_channels.py in $LiveTree" }
if (-not (Test-Path -LiteralPath (Join-Path $Registry "ROOT_PIN.json"))) { throw "no ROOT_PIN.json in ${Registry}: run the bootstrap first." }
$Python = (Get-Content -Raw (Join-Path $AuthHome "config.json") | ConvertFrom-Json).python
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { throw "no python in $AuthHome\config.json" }

$Sealed = Join-Path $AuthHome "sealed"
New-Item -ItemType Directory -Force -Path $Sealed | Out-Null
& icacls $Sealed /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Users:(OI)(CI)RX" | Out-Null
foreach ($f in $Files) { Copy-Item -Force -LiteralPath (Join-Path $Src $f) -Destination (Join-Path $Sealed $f) }
Copy-Item -Force -LiteralPath $Channels -Destination (Join-Path $Sealed "alert_channels.py")
# the SEALED channel config (and the delivery ledger beside it): never the live tree's copy
$SecretsDst = Join-Path $Sealed "data\secrets"
New-Item -ItemType Directory -Force -Path $SecretsDst | Out-Null
& icacls $SecretsDst /inheritance:r /grant:r "Administrators:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
$Copied = 0
foreach ($f in @("alert_channels.json", "heartbeat_url.json")) {
    $src = Join-Path $LiveTree "data\secrets\$f"
    if (Test-Path -LiteralPath $src) { Copy-Item -Force -LiteralPath $src -Destination (Join-Path $SecretsDst $f); $Copied++ }
}
if (-not (Test-Path -LiteralPath (Join-Path $SecretsDst "alert_channels.json"))) { throw "no data\secrets\alert_channels.json on the box: no ROOT notice could ever be delivered." }
$hashes = foreach ($f in $Files + @("alert_channels.py")) { "{0} {1}" -f (Get-FileHash -Algorithm SHA256 (Join-Path $Sealed $f)).Hash.ToLower(), $f }
$hashes | Set-Content -LiteralPath (Join-Path $Sealed "INSTALLED.sha256") -Encoding ASCII

# a dry check before the task exists: it must run and judge (no ROOT merge in flight -> CLEAR)
$args_ = @("-I", (Join-Path $Sealed "repin.py"), "--registry", $Registry, "--live-tree", $LiveTree)
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
Write-Host "Notices and alerts go through the sealed notifier; everything is also logged to $Registry\repin.log.jsonl."
