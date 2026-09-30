# Register MT5-OffsiteBackup: encrypted, versioned, off-site copy of the box-only data every 6 hours.
#
# offsite_backup.py drives restic (client-side AES-256; the destination only ever holds
# ciphertext) over C:\moat\bronze, data\tape and the terminal profile. data\secrets and the
# terminal's accounts.dat are hard-excluded: they never leave the box. Daily forget --prune keeps
# 24 hourly / 30 daily / 12 weekly / 24 monthly; weekly `check --read-data-subset` is the restore
# evidence. Without data\secrets\offsite_backup.json it records NOT_ARMED; without restic,
# NO_RESTIC. Both exit 0 and show in OPS_REDUNDANCY.json.
#
# -InstallRestic downloads the pinned restic release from GitHub into C:\opt\restic first.
param([switch]$InstallRestic)

if ($InstallRestic -and -not (Test-Path 'C:\opt\restic\restic.exe')) {
  $v = '0.17.3'
  $zip = "$env:TEMP\restic_$v.zip"
  Invoke-WebRequest -UseBasicParsing -OutFile $zip `
    "https://github.com/restic/restic/releases/download/v$v/restic_${v}_windows_amd64.zip"
  New-Item -ItemType Directory -Force 'C:\opt\restic' | Out-Null
  Expand-Archive -Force $zip 'C:\opt\restic'
  Get-ChildItem 'C:\opt\restic\restic_*.exe' | Select-Object -First 1 |
    Move-Item -Destination 'C:\opt\restic\restic.exe' -Force
  Write-Output ("restic: " + (& 'C:\opt\restic\restic.exe' version))
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
  '/d /s /c cd /d C:\opt\quant && ' +
  '"C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe" -u -W ignore ' +
  'desks\mt5\scripts\offsite_backup.py >> C:\opt\quant\desks\mt5\logs\MT5-OffsiteBackup.log 2>&1')

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(43) `
             -RepetitionInterval (New-TimeSpan -Hours 6)

# BelowNormal priority and IgnoreNew: the first upload is ~14 GB and must never stack or starve
# the gateway; later runs upload only new ticks.
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Priority 7 `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Hours 5) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-OffsiteBackup' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-OffsiteBackup'
Write-Output ("MT5-OffsiteBackup registered: " + $t.State)
