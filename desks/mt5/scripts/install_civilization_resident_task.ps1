# INSTALL THE 24/7 RESEARCH-CIVILIZATION RESIDENT (2026-09-30, principal's order).
#
# One long-running task: `research\civilization_resident.py --loop`, which mines the
# civilization lanes (QuantConnect, WorldQuant, Man AHL, Bridgewater, AQR, Two Sigma, D. E. Shaw,
# Winton, market makers, Renaissance archaeology) continuously and sleeps only until the next
# lane is due. It is NOT the only clock: the hourly `global_mining` leg runs the same lanes
# whenever this loop's heartbeat is older than 20 minutes, so a stopped or crashed resident
# costs at most one hour of latency, never an idle lane.
#
# Starts at boot and restarts on failure (3 tries, 5 minutes apart); MultipleInstances
# IgnoreNew because two loops would fetch the same cursors. Takes its principal from
# MT5-MoatSilver like every other MT5 organ.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_civilization_resident_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-CivilizationResident'
$Root     = 'C:\opt\quant\desks\mt5'
$Log      = 'C:\opt\quant\desks\mt5\logs\MT5-CivilizationResident.log'

$template = Get-ScheduledTask -TaskName 'MT5-MoatSilver'
$userId   = $template.Principal.UserId

$action = New-ScheduledTaskAction -Execute 'cmd.exe' `
    -Argument ('/d /s /c "cd /d {0} && py -3 research\civilization_resident.py --loop --budget-s 600 >> {1} 2>&1"' -f $Root, $Log)
$trigger   = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType S4U -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Output "registered and started $TaskName"
