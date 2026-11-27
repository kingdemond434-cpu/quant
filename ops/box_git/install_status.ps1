<#
.SYNOPSIS
  Publish the box's desk status off-box every hour (ops/box_git/status_push.py), once.

.DESCRIPTION
  Desk health B13 (11-24): with the box's Claude link down nobody could see whether E8, FTMO and
  Fusion traded. This makes a box-native hourly task that pushes allow-listed, scrubbed reports
  to the `status` branch of a SEPARATE, PRIVATE, status-only GitLab project (never the drop
  project, whose CLEAR binds "box key = read-only"; Audit MF-2). Claude is not in the path.
    1. Makes the box's own ed25519 STATUS key in <forge>\status-key (Administrators and SYSTEM
       only). It is a different key from the read-only drop key; the private key never leaves.
    2. Adds "status" to <forge>\loop.json (every other field kept).
    3. Registers QuantForge-Status (SYSTEM, hourly, runs the loop's gate-merged checkout).
    4. Prints the PUBLIC key: register it, WITH write access, on the status-only project only.
       That project holds equity and positions: keep it private and never mirror it.
  Idempotent. Run as Administrator.
#>
param(
    [Parameter(Mandatory = $true)] [string] $StatusUrl,   # git@gitlab.com:<owner>/<status>.git
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Desk = "C:\opt\quant"
)
$ErrorActionPreference = "Stop"
if ($StatusUrl -notmatch '^git@gitlab\.com:[A-Za-z0-9._/-]+\.git$') {
    throw "StatusUrl must look like git@gitlab.com:<owner>/<repo>.git"
}
$Forge = Join-Path $Root "forge"
$cfgPath = Join-Path $Forge "loop.json"
if (-not (Test-Path -LiteralPath $cfgPath)) { throw "no ${cfgPath}: install the forge first" }
$keyDir = Join-Path $Forge "status-key"
$key = Join-Path $keyDir "status_ed25519"
$null = New-Item -ItemType Directory -Force -Path $keyDir
& icacls $keyDir /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" | Out-Null
if (-not (Test-Path -LiteralPath $key)) {
    $kg = (Get-Command ssh-keygen -ErrorAction SilentlyContinue).Source
    if (-not $kg) { $kg = "C:\Program Files\Git\usr\bin\ssh-keygen.exe" }
    & $kg -q -t ed25519 -N '""' -C "quant-box-status" -f $key
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $key)) { throw "ssh-keygen failed" }
}
& icacls $key /inheritance:r /grant:r "*S-1-5-32-544:F" "*S-1-5-18:F" | Out-Null

$files = @(
    "desks/mt5/data/account_state.json", "desks/mt5/data/E8_ACCOUNT.json",
    "data/account_positions.json", "desks/mt5/reports/EXIT_ACCOUNTS.json",
    "desks/mt5/reports/CROSS_ACCOUNT_DIVERGENCE.json", "desks/mt5/reports/JUDGING_THROUGHPUT.json",
    "desks/mt5/reports/LLM_BUDGET_CENSUS.json", "desks/mt5/reports/CN_MODEL_ENSEMBLE.json",
    "desks/mt5/data/RELEASE.json")
$cfg = Get-Content -LiteralPath $cfgPath -Raw | ConvertFrom-Json
if ($cfg.drop -and ($cfg.drop.url.TrimEnd('/') -replace '\.git$', '') -ieq ($StatusUrl.TrimEnd('/') -replace '\.git$', '')) {
    throw "StatusUrl equals the drop url: the box never writes to the drop project"
}
$status = [pscustomobject]@{ url = $StatusUrl; key = $key; checkout = (Join-Path $Forge "status-co")
                             root = $Desk; files = $files }
if ($cfg.PSObject.Properties.Name -contains "status") { $cfg.status = $status }
else { $cfg | Add-Member -NotePropertyName status -NotePropertyValue $status }
$tmp = "$cfgPath.part"
$cfg | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $tmp -Encoding ascii
Move-Item -LiteralPath $tmp -Destination $cfgPath -Force

$py = $cfg.python
$src = Join-Path $Forge "loop-src"
$act = New-ScheduledTaskAction -Execute $py -Argument ("`"{0}`" --config `"{1}`"" -f (Join-Path $src "ops\box_git\status_push.py"), $cfgPath)
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 15)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable
Register-ScheduledTask -TaskName "QuantForge-Status" -Action $act -Trigger $trg -Settings $set `
    -User "SYSTEM" -RunLevel Highest -Force | Out-Null

Write-Output "STATUS CONFIGURED url=$StatusUrl branch=status (task QuantForge-Status, pushes hourly)"
Write-Output ("PUBLIC KEY: " + (Get-Content -LiteralPath "$key.pub" -Raw).Trim())
