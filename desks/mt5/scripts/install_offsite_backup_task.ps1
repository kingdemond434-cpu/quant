# Register MT5-OffsiteBackup: encrypted, versioned, off-site copy of the box-only data every 6 hours.
#
# offsite_backup.py drives restic (client-side AES-256; the destination only ever holds
# ciphertext) over C:\moat\bronze, data\tape and the terminal profile. data\secrets and the
# terminal's accounts.dat are hard-excluded: they never leave the box. Daily forget --prune keeps
# 24 hourly / 30 daily / 12 weekly / 24 monthly; weekly `check --read-data-subset` is the restore
# evidence. Without data\secrets\offsite_backup.json it records NOT_ARMED; without restic,
# NO_RESTIC. Both exit 0 and show in OPS_REDUNDANCY.json.
#
# -InstallRestic downloads the pinned restic release from GitHub into C:\opt\restic first, and
# refuses it unless its SHA-256 equals the digest GitHub publishes for that release asset.
# -InitLocal arms a repository on this box's own disk (C:\backup\restic) with a random key the
# box generates and keeps in data\secrets (never printed), so versioned snapshots and the restore
# drill start before an off-site destination exists. Its verdict stays LOCAL_ONLY until the
# repository is pointed off-site; an existing config is never replaced.
param([switch]$InstallRestic, [switch]$InitLocal)

$ErrorActionPreference = 'Stop'
$repo = 'C:\opt\quant'
$py = @((Join-Path $repo '.venv\Scripts\python.exe'),
        'C:\Program Files\Python314\python.exe',
        'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe') |
      Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { throw 'no python.exe found in .venv or either Python314 install' }

if ($InstallRestic -and -not (Test-Path 'C:\opt\restic\restic.exe')) {
  $v = '0.17.3'
  $name = "restic_${v}_windows_amd64.zip"
  $zip = "$env:TEMP\$name"
  Invoke-WebRequest -UseBasicParsing -OutFile $zip `
    "https://github.com/restic/restic/releases/download/v$v/$name"
  $rel = Invoke-RestMethod -UseBasicParsing "https://api.github.com/repos/restic/restic/releases/tags/v$v"
  $want = (($rel.assets | Where-Object { $_.name -eq $name }).digest -replace '^sha256:', '').ToLower()
  $got = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
  if (-not $want -or $want -ne $got) {
    Remove-Item $zip -Force
    throw "restic $v archive sha256 $got does not match the published digest '$want'; nothing installed"
  }
  Write-Output "restic $v archive sha256 $got matches the published digest"
  New-Item -ItemType Directory -Force 'C:\opt\restic' | Out-Null
  Expand-Archive -Force $zip 'C:\opt\restic'
  Get-ChildItem 'C:\opt\restic\restic_*.exe' | Select-Object -First 1 |
    Move-Item -Destination 'C:\opt\restic\restic.exe' -Force
  Write-Output ("restic: " + (& 'C:\opt\restic\restic.exe' version))
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"' + $py + '" -u -W ignore ' +
  'desks\mt5\scripts\offsite_backup.py >> C:\opt\quant\desks\mt5\logs\MT5-OffsiteBackup.log 2>&1')

if ($InitLocal) {
  New-Item -ItemType Directory -Force 'C:\backup\restic' | Out-Null
  & $py (Join-Path $repo 'desks\mt5\scripts\offsite_backup.py') --init-local 'C:\backup\restic'
}

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(43) `
             -RepetitionInterval (New-TimeSpan -Hours 6)

# BelowNormal priority and IgnoreNew: the first run reads ~75 GB (ticks 25, tape 21, terminal 29;
# measured 2026-10-29) and must never stack or starve
# the gateway; later runs upload only new ticks.
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Priority 7 `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 5) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-OffsiteBackup' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-OffsiteBackup'
Write-Output ("MT5-OffsiteBackup registered: " + $t.State)
