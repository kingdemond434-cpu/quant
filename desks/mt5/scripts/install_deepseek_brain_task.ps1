# REGISTER THE DEEPSEEK THIRD BRAIN ON THIS BOX (2026-10-20).
#
# WHY. `ops/quant-deepseek.timer` is a systemd unit for the Linux box; this Windows host has no
# systemd and no logged-in user at night, so the third brain only ran when another machine was
# awake. The addendum requires a permanent 24/7 laboratory on the desk's own runtime. This
# registers ONE task, `MT5-DeepSeek`, hourly, running whether or not anyone is logged on.
#
# THE TRIGGER SHAPE IS THE STALL WATCHDOG'S, FOR ITS REASON. A daily trigger repeating every
# hour for one day re-arms itself every midnight; a `-Once` trigger with a long repetition
# duration has expired on this box before (MEASURED 2026-09-22: Next Run Time went to N/A and
# nothing shipped for four days). Offset to :24 so it does not land on the merge docket (:14,
# :44) or the gauntlet's :00/:05 slots.
#
# THE PRINCIPAL IS KEPT WHEN THE TASK EXISTS, NEVER REASSIGNED. Two registrations with two
# identities is a coin toss about which one runs. A fresh box gets SYSTEM / ServiceAccount /
# Highest, which fires with nobody logged on.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_deepseek_brain_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-DeepSeek'
$Repo     = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Script   = Join-Path $Repo 'ops\run_deepseek_windows.ps1'
if (-not (Test-Path $Script)) { throw "run_deepseek_windows.ps1 missing at $Script" }
$LogDir   = Join-Path $Repo 'desks\mt5\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log      = Join-Path $LogDir 'MT5-DeepSeek.log'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $Repo -Argument (
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" >> "{1}" 2>&1' -f $Script, $Log)

$start = (Get-Date).Date.AddMinutes(24)
$trigger = New-ScheduledTaskTrigger -Daily -At $start
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -MultipleInstances IgnoreNew

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    $principal = New-ScheduledTaskPrincipal -UserId $existing.Principal.UserId `
        -LogonType $existing.Principal.LogonType -RunLevel Highest
    "keeping principal {0} ({1})" -f $existing.Principal.UserId, $existing.Principal.LogonType
} else {
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
}

if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Hourly DeepSeek third-brain research cycle: point-in-time research packet, cold Phase A, sealed output, typed findings donated into the one canonical compiler. Research generation only; cannot promote, size or merge. Installed 2026-10-20 so the organ runs with no session and no laptop.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 8
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"report: desks\mt5\reports\DEEPSEEK_RESEARCH.json; log: $Log"
