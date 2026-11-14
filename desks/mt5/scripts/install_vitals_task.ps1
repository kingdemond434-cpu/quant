# REGISTER MT5-Vitals -- THE DESK'S LIVE STATE, REWRITTEN EVERY FIVE SECONDS (2026-11-13).
#
# research\vitals.py --serve folds the artifacts the box's organs already write into
# reports\VITALS.json, every section stamped with its own "at". It reads files only: no terminal,
# no order, no git write. MT5-ShadowSync publishes the file ($reportPaths).
#
# A resident: at start-up, and re-armed every five minutes so a crash costs at most five minutes
# (IgnoreNew makes a re-arm a no-op while it lives). SYSTEM, below-normal priority.
#
# IDEMPOTENT. -IfMissing does nothing when the task exists.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_vitals_task.ps1
param([switch]$IfMissing, [switch]$DryRun)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-Vitals'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'research\vitals.py'
$Log      = Join-Path $DeskRoot 'logs\MT5-Vitals.log'
$py       = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Script)) { throw "vitals.py missing at $Script" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument (
    '/d /s /c cd /d "' + $DeskRoot + '" && "' + $py + '" -u -W ignore "' + $Script + '" ' +
    '--serve --every 5 >> "' + $Log + '" 2>&1') -WorkingDirectory $DeskRoot

$boot = New-ScheduledTaskTrigger -AtStartup
# A DAILY trigger repeating every five minutes for one day re-arms itself at midnight and never
# expires (a -Once trigger with a long duration expired on this box on 2026-09-21).
$start = (Get-Date).Date
$keep = New-ScheduledTaskTrigger -Daily -At $start
$keep.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -Priority 7

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if ($DryRun) {
    'DRYRUN would register {0}: at start-up + every 5 min keep-alive, SYSTEM, runs {1} --serve' -f $TaskName, $Script
    exit 0
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($boot, $keep) `
    -Principal $principal -Settings $settings `
    -Description "Desk VITALS (research\vitals.py --serve): live state every 5 s, reports\VITALS.json." | Out-Null
Start-ScheduledTask -TaskName $TaskName
$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} runs={2} --serve" -f $t.TaskName, $t.State, $Script
