# RE-POINT THE TWO BOX WATCHERS AT THEIR CANON COPIES IN THIS REPO (2026-10-21).
#
# MT5-FTMOFollow and MT5-E8WindowGuard were registered by hand on the trading box against
# C:\opt\quant-ops\ftmo_follow.py and C:\opt\quant-ops\e8_window_guard.py, a directory no release
# carries. desks\mt5\scripts\watchers\ now holds both, byte-identical to the box originals apart
# from a header comment (pinned by desks\mt5\tests\test_box_watchers_canon.py). This file changes
# the script path in each task's action and pins the two battery switches (see below); the
# registration is otherwise the one the box runs:
#
#   principal  S-1-5-18 (SYSTEM), ServiceAccount, RunLevel Highest (XML: HighestAvailable)
#   trigger    every 1 minute (PT1M), indefinitely
#   settings   MultipleInstances IgnoreNew, ExecutionTimeLimit PT5M, StartWhenAvailable,
#              AllowStartIfOnBatteries, DontStopIfGoingOnBatteries
#   action     cmd.exe /d /s /c "cd /d C:\opt\quant && "<python>" -u -W ignore <script>
#                 >> C:\opt\quant\desks\mt5\logs\<task>.log 2>&1"
#
# The two battery switches are SET HERE, not inherited: New-ScheduledTaskSettingsSet defaults to
# DisallowStartIfOnBatteries + StopIfGoingOnBatteries, and a guard that cancels orders must run
# like an always-on server whatever the host reports about its power source.
#
# Idempotent: an existing task is updated in place (Set-ScheduledTask), a missing one registered,
# and the action/principal/trigger/settings are read back from the scheduler and printed, so the
# run can be checked from the window that launched it. No other task is touched; nothing is started.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_box_watchers_canon.ps1

[CmdletBinding()]
param(
    [string] $RepoRoot = "C:\opt\quant",
    [string] $Python   = "C:\Program Files\Python314\python.exe"
)
$ErrorActionPreference = 'Stop'

$watchers = Join-Path $RepoRoot "desks\mt5\scripts\watchers"
$logs     = Join-Path $RepoRoot "desks\mt5\logs"
if (-not (Test-Path $Python)) { throw "python missing at $Python" }
if (-not (Test-Path $logs))   { throw "log directory missing at $logs" }

$tasks = [ordered]@{
    'MT5-FTMOFollow'    = (Join-Path $watchers 'ftmo_follow.py')
    'MT5-E8WindowGuard' = (Join-Path $watchers 'e8_window_guard.py')
}

$principal = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
$settings  = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
                -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

foreach ($name in $tasks.Keys) {
    $script = $tasks[$name]
    if (-not (Test-Path $script)) { throw "$name script missing at $script" }
    $log = Join-Path $logs ("{0}.log" -f $name)
    $arguments = ('/d /s /c "cd /d {0} && "{1}" -u -W ignore {2} >> {3} 2>&1"' -f $RepoRoot, $Python, $script, $log)
    $action  = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date) -RepetitionInterval (New-TimeSpan -Minutes 1)

    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host ("{0}: was  {1} {2}" -f $name, $existing.Actions[0].Execute, $existing.Actions[0].Arguments)
        Set-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings | Out-Null
        Write-Host ("{0}: updated" -f $name)
    } else {
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
            -Principal $principal -Settings $settings | Out-Null
        Write-Host ("{0}: registered (was absent)" -f $name)
    }

    $t = Get-ScheduledTask -TaskName $name
    Write-Host ("{0}: now  {1} {2}" -f $name, $t.Actions[0].Execute, $t.Actions[0].Arguments)
    Write-Host ("    principal {0} / {1} / {2}" -f $t.Principal.UserId, $t.Principal.LogonType, $t.Principal.RunLevel)
    Write-Host ("    trigger   every {0} for {1}" -f $t.Triggers[0].Repetition.Interval, $(if ($t.Triggers[0].Repetition.Duration) { $t.Triggers[0].Repetition.Duration } else { 'indefinitely' }))
    Write-Host ("    settings  {0} / limit {1} / StartWhenAvailable {2}" -f $t.Settings.MultipleInstances, $t.Settings.ExecutionTimeLimit, $t.Settings.StartWhenAvailable)
    Write-Host ("    battery   DisallowStartIfOnBatteries {0} / StopIfGoingOnBatteries {1}" -f $t.Settings.DisallowStartIfOnBatteries, $t.Settings.StopIfGoingOnBatteries)
    Write-Host ("    state     {0}" -f $t.State)
}
