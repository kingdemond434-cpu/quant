<#
.SYNOPSIS
    Register the two CRO cycle lanes, MT5-CycleNoon (Claude) and MT5-CycleMidnight (Codex), and
    nothing else.

.DESCRIPTION
    Both lanes run desks\mt5\scripts\Run-DeskCycle.ps1, which executes docs\cro\CRO_CYCLE.md.

    WHY THIS EXISTS BESIDE THE INSTALLER TABLE (2026-09-29). The lanes were registered as `-Once`
    at today's 12:00/00:00 with an ELEVEN-HOUR repetition. A -Once trigger's repetition ends when
    its duration ends, so each lane fired on the day it was registered and never again. The shape
    that repeats forever is the one MT5-AdoptRelease uses: a -Daily trigger whose Repetition is
    copied from a -Once trigger (PowerShell 5.1's -Daily set rejects -RepetitionInterval).

    HOURLY, ALL DAY, ON PURPOSE. The lane window is decided by the launcher on the Europe/Dublin
    clock (NOON 12:00-22:59, MIDNIGHT 00:00-10:59), so the box's own time zone and DST rules cannot
    move the principal's 12:00 Irish slot. A firing outside the window exits 0 after one clock read.

    THE ACCOUNT IS THE ONE THAT HOLDS THE CLI LOGIN. `claude` and `codex` keep their credentials in
    the user profile. Under SYSTEM (the default for this box's headless tasks) neither CLI is logged
    in and the lane exits 3 every day. So the lanes run as -RunAs (default: the account running this
    script) with LogonType S4U: headless, survives logoff, no password stored.

    Re-running the whole Install-QuantWindows.ps1 on a live box has failed with "Access is denied";
    this touches two tasks.

.PARAMETER RunAs
    Account whose profile holds the claude/codex logins. Default: the current user.

.PARAMETER NoStart
    Register only; do not fire a WhatIf check.
#>
[CmdletBinding()]
param(
    [string] $RunAs = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME),
    [switch] $NoStart
)
$ErrorActionPreference = 'Stop'

# THE LANES MUST NOT RUN AS SYSTEM (measured 2026-10-28). MT5-CycleMidnight was found registered as
# SYSTEM with the old one-shot trigger: Last Run 1999, result 267011 (never run), no next run.
# Under SYSTEM neither CLI is logged in, so even a repaired trigger would exit 3 every day.
if ($RunAs -match '^(NT AUTHORITY\\)?(SYSTEM|LOCAL SYSTEM)$' -or $RunAs -match '\\\$?SYSTEM$' -or $RunAs -eq 'S-1-5-18') {
    throw "RunAs '$RunAs' is SYSTEM: neither claude nor codex is logged in there. Pass -RunAs <the account that ran 'codex login' and 'claude /login'>."
}

$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Launcher = Join-Path $DeskRoot 'scripts\Run-DeskCycle.ps1'
if (-not (Test-Path $Launcher)) { throw "Run-DeskCycle.ps1 missing at $Launcher" }
$ps = (Get-Command powershell.exe).Source

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 10) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $RunAs -LogonType S4U -RunLevel Highest

foreach ($lane in @(
        @{ Name = 'MT5-CycleNoon';     Lane = 'noon';     Desc = 'CRO cycle, Claude lane: docs\cro\CRO_CYCLE.md at 12:00 Europe/Dublin (window gated by the launcher).' },
        @{ Name = 'MT5-CycleMidnight'; Lane = 'midnight'; Desc = 'CRO cycle, Codex lane: docs\cro\CRO_CYCLE.md at 00:00 Europe/Dublin (window gated by the launcher).' })) {
    $action = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $RepoRoot -Argument `
        ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -Lane {1}' -f $Launcher, $lane.Lane)
    # Minute 2 of every hour: clear of the :05/:12/:20 git writers' starts.
    $trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(2))
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(2)) `
        -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
    Unregister-ScheduledTask -TaskName $lane.Name -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $lane.Name -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $lane.Desc | Out-Null
    $t = Get-ScheduledTask -TaskName $lane.Name
    $i = Get-ScheduledTaskInfo -TaskName $lane.Name
    "installed {0}: state={1} runas={2} logon={3} every={4} next={5}" -f $t.TaskName, $t.State,
        $t.Principal.UserId, $t.Principal.LogonType, $t.Triggers[0].Repetition.Interval, $i.NextRunTime
    # A registration with no next run is the defect this script exists to end: say so in the exit code.
    if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
        Write-Host ("FATAL: {0} registered with no next run time" -f $lane.Name)
        exit 4
    }
}

if (-not $NoStart) {
    foreach ($lane in 'noon', 'midnight') {
        & $ps -NoProfile -ExecutionPolicy Bypass -File $Launcher -Lane $lane -WhatIfOnly | Select-Object -First 3
    }
}
