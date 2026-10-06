# REGISTER MT5-STALLWATCH ON ITS OWN, AND RUN IT NOW (2026-09-30).
#
# WHY A STANDALONE INSTALLER. MT5-StallWatch is the box's ten-minute healer and, since PR #141,
# the INDEPENDENT pager for a dead state publisher: it runs
# `py -3 -m libs.ops.state_publication --watch`, which pages STALLED / SOURCE_STALE / METER_SILENT
# even when the hourly cycle that writes BOX_STATE_FLOW.json has died, and it writes
# `alerts_armed` / `alerts_line` into data\stall_watch.json. It had no installer of its own: the
# only registration was one row of Install-QuantWindows.ps1's table, and box_tasks.manifest said
# installer="NONE" -- so on a box where that whole installer cannot be re-run (it has failed with
# "Access is denied" on a live box), the one task that pages a stall could not be put back
# without it. This touches ONE task.
#
# WHAT IT DOES. Registers MT5-StallWatch to run desks\mt5\scripts\stall_watch.ps1 every TEN
# minutes through powershell (never through python: a .ps1 run by the interpreter "fails" as a
# SyntaxError that reads like a busy watchdog), logging to desks\mt5\logs\MT5-StallWatch.log,
# then STARTS it so the first pass happens now.
#
# THE TRIGGER SHAPE IS THE PLUMBING WATCHDOG'S, FOR ITS REASON. A DAILY trigger repeating every
# ten minutes for one day, never a -Once trigger with a long RepetitionDuration: MEASURED
# 2026-09-22, the scheduler folded MT5-AdoptRelease's long duration into `P9DT2H40M`, the
# repetition EXPIRED, Next Run Time went to N/A, and nothing shipped reached the box for four
# days. A daily trigger re-arms itself every midnight and has no end to expire. Offset to :03 so
# it does not land on the :05/:20/:35/:50 ShadowSync slots or the :12 adoption.
#
# THE PRINCIPAL IS KEPT, NEVER CHANGED. Re-running an installer on a live box has failed with
# "Access is denied" on the S4U principals, and Install-QuantWindows.ps1's table registers this
# task too -- two registrations with two identities is a coin toss about which one runs. So when
# the task already exists its principal (UserId + LogonType, S4U included) is carried over
# unchanged and only the trigger, action and settings are replaced; a fresh box gets the table's
# identity, SYSTEM / ServiceAccount / Highest, which a healer needs to re-enable other tasks and
# which fires with nobody logged on.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_stall_watch_task.ps1

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-StallWatch'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Script   = Join-Path $DeskRoot 'scripts\stall_watch.ps1'
if (-not (Test-Path $Script)) { throw "stall_watch.ps1 missing at $Script" }
$LogDir   = Join-Path $DeskRoot 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log      = Join-Path $LogDir 'MT5-StallWatch.log'

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $DeskRoot -Argument `
    ("/d /s /c `"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"{0}`" >> `"{1}`" 2>&1`"" -f $Script, $Log)

$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(3))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(3)) `
    -RepetitionInterval (New-TimeSpan -Minutes 10) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# StartWhenAvailable so a pass missed to a reboot is caught up; IgnoreNew so a slow pass is never
# stacked on itself; nine minutes so a pass that outlives its own interval is killed and named in
# the task history rather than running into the next one.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 9) -MultipleInstances IgnoreNew

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    # Keep the box's identity for this task exactly as it is (S4U stays S4U).
    $principal = New-ScheduledTaskPrincipal -UserId $existing.Principal.UserId `
        -LogonType $existing.Principal.LogonType -RunLevel Highest
    "keeping principal {0} ({1})" -f $existing.Principal.UserId, $existing.Principal.LogonType
} else {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
}

if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Every 10 minutes: heal stacked, stalled and Disabled research tasks; page a dead state publisher (libs.ops.state_publication --watch); never touches the money path." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2}" -f $t.TaskName, $t.State, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"state: desks\mt5\data\stall_watch.json (alerts_armed / alerts_line); log: $Log"
