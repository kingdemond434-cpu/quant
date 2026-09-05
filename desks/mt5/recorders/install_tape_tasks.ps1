# THE SCHEDULE. A component without one is a component that runs when someone remembers.
#
#   powershell -ExecutionPolicy Bypass -File desks\mt5\recorders\install_tape_tasks.ps1
#   powershell -ExecutionPolicy Bypass -File ...\install_tape_tasks.ps1 -WhatIf   # print only
#
# FOUR TASKS, AND THE CADENCE OF EACH IS AN ARGUMENT ABOUT WHAT IS LOST BY WAITING.
#
#   MT5-TickRecorder    CONTINUOUS, restarted on failure, started at boot and at logon.
#                       This is the only one whose cadence is not a preference. Every second the
#                       recorder is not running is a second of quotes that no vendor sells and
#                       this desk can never buy. It runs as a resident loop with its own 60s
#                       beat, so the task's job is only to make sure the process EXISTS -- hence
#                       RestartCount 9999 and a 1-minute restart interval. There is no
#                       ExecutionTimeLimit: a recorder killed by a scheduler timeout is a
#                       recorder that stops recording every N hours, silently, forever.
#
#   MT5-TickIntegrity   HOURLY. The tape is only worth what it can be proven to be, and the
#                       proof must arrive while the recorder can still be fixed. It exits 2 on
#                       FAIL, which the scheduler records as a failed task -- that is the point:
#                       a hole in the tape should look like a broken job, not like a JSON file
#                       nobody opened.
#
#   MT5-TapeFeatures    HOURLY, at :20. Every miner hourly minimum (principal 2026-09-05). The
#                       pass is incremental against a content watermark, so an hourly run that
#                       finds nothing new costs a directory listing.
#
#   MT5-VolArchive      HOURLY, at :40. Second priority behind the tape and deliberately so: a
#                       missed hour of vol observations costs one intraday snapshot of a daily
#                       series, while a missed hour of ticks costs every quote in it. Hourly
#                       rather than daily because the public series restate intraday and the
#                       vintage IS the asset.
#
# WHY THE RECORDER IS ITS OWN PROCESS AND NOT A THREAD IN THE GATEWAY. The gateway must never
# wait on a disk write -- a recorder that can stall an order is a recorder that loses money --
# and the cheapest way to guarantee that is for the writer to live somewhere the gateway cannot
# call into. It also means a recorder crash cannot take the gateway with it, and a gateway
# restart does not cost a second of tape.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = "C:\opt\quant",
    [string]$Python   = "py",
    [string]$TapeRoot = "C:\mt5tape",
    [string]$RunAsUser = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = "Stop"
$desk = Join-Path $RepoRoot "desks\mt5"

if (-not (Test-Path $desk)) {
    Write-Error "desk not found at $desk -- pass -RepoRoot"
    exit 1
}

# The tape root is created here rather than by the recorder's first write, so a permissions
# problem surfaces at install time with a person present, not at 03:00 as a WRITE_FAILED gap row.
if (-not (Test-Path $TapeRoot)) {
    New-Item -ItemType Directory -Path $TapeRoot -Force | Out-Null
    Write-Host "created tape root $TapeRoot"
}

function Install-DeskTask {
    param(
        [string]$Name,
        [string]$Module,
        [string]$Arguments = "",
        [object]$Trigger,
        [switch]$Continuous
    )
    $args = "-3 -m $Module $Arguments".Trim()
    $action = New-ScheduledTaskAction -Execute $Python -Argument $args -WorkingDirectory $desk
    $settingsArgs = @{
        AllowStartIfOnBatteries    = $true
        DontStopIfGoingOnBatteries = $true
        StartWhenAvailable         = $true
        MultipleInstances          = "IgnoreNew"
    }
    if ($Continuous) {
        # NO ExecutionTimeLimit AND AGGRESSIVE RESTART. See the header: a scheduler timeout on
        # the recorder is a scheduled, silent, permanent hole in the tape.
        $settingsArgs["ExecutionTimeLimit"]  = [TimeSpan]::Zero
        $settingsArgs["RestartCount"]        = 9999
        $settingsArgs["RestartInterval"]     = (New-TimeSpan -Minutes 1)
    } else {
        $settingsArgs["ExecutionTimeLimit"] = (New-TimeSpan -Minutes 50)
    }
    $settings = New-ScheduledTaskSettingsSet @settingsArgs

    if ($PSCmdlet.ShouldProcess($Name, "register scheduled task")) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
        Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger `
            -Settings $settings -User $RunAsUser -RunLevel Highest | Out-Null
        Write-Host "installed $Name  ->  $Python $args"
    } else {
        Write-Host "WHATIF $Name  ->  $Python $args"
    }
}

$env:MT5_TAPE_ROOT = $TapeRoot
[Environment]::SetEnvironmentVariable("MT5_TAPE_ROOT", $TapeRoot, "Machine")

# --- 1. THE RECORDER. Boot + logon, resident, restarted forever.
$bootTrigger  = New-ScheduledTaskTrigger -AtStartup
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn
Install-DeskTask -Name "MT5-TickRecorder" -Module "recorders.tick_recorder" `
    -Trigger @($bootTrigger, $logonTrigger) -Continuous

# --- 2. THE PROOF. Hourly on the hour; nonzero exit on FAIL is the alarm.
Install-DeskTask -Name "MT5-TickIntegrity" -Module "recorders.tick_integrity" `
    -Arguments "--days 10" `
    -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
        -RepetitionInterval (New-TimeSpan -Hours 1))

# --- 3. THE FEATURES. Hourly at :20, incremental against a content watermark.
Install-DeskTask -Name "MT5-TapeFeatures" -Module "recorders.tape_features" `
    -Arguments "--days 10" `
    -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(20) `
        -RepetitionInterval (New-TimeSpan -Hours 1))

# --- 4. THE VOL ARCHIVE. Hourly at :40, second priority behind the tape.
Install-DeskTask -Name "MT5-VolArchive" -Module "recorders.vol_archive" `
    -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(40) `
        -RepetitionInterval (New-TimeSpan -Hours 1))

Write-Host ""
Write-Host "SMOKE THE RECORDER BEFORE TRUSTING THE SCHEDULE -- one cycle, printed:"
Write-Host "  cd $desk"
Write-Host "  $Python -3 -m recorders.tick_recorder --once"
Write-Host "  $Python -3 -m recorders.tick_integrity --days 1"
Write-Host ""
Write-Host "Then confirm the tape is actually growing (this is the check that matters):"
Write-Host "  Get-ChildItem -Recurse $TapeRoot\ticks | Measure-Object -Property Length -Sum"
Write-Host ""
Write-Host "WHAT TO EXPECT ON DAY TWO, so a normal thing is not read as a problem. A day being"
Write-Host "recorded holds one segment per cycle -- ~1,440 parquet files, ~5 MB per symbol -- and"
Write-Host "that is 85% container, not ticks. Roughly six hours after a day ends the recorder"
Write-Host "COMPACTS it to a single segment, which is measured at ~25x smaller and loses nothing."
Write-Host "So the tape's size should SAW: climb through the day, drop sharply the next morning."
Write-Host "A tape that only ever climbs means compaction is not running -- check the recorder's"
Write-Host "cycle output for 'compacted N day(s)' and reports\TICK_INTEGRITY.json for"
Write-Host "totals.sealed_but_uncompacted, which counts finished days still carrying containers:"
Write-Host "  $Python -3 -m recorders.tick_integrity --days 3"
Write-Host "  Get-Content ..\reports\TICK_INTEGRITY.json | ConvertFrom-Json |"
Write-Host "    Select-Object -ExpandProperty totals"
