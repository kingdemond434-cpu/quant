<#
  THE CLOCKS THE INSTALLER DECLARES AND THE SCHEDULER DID NOT HAVE (2026-09-23).

  `check_declared_tasks` reported five tasks declared by the box's own manifest and ABSENT from
  the scheduler. Re-running Install-QuantWindows.ps1 whole on a live box has failed with "Access
  is denied" on the S4U principals, so this registers exactly those tasks, with the triggers and
  the scripts the installer's own table declares, and nothing else.

  MT5-ArtifactSync is NOT here: the installer deliberately UNREGISTERS it (the Hetzner sync it
  fed was decommissioned 2026-08-23). The manifest's claim on it is the thing that was wrong,
  and the manifest is where that is fixed.
#>
$ErrorActionPreference = 'Continue'
$RepoRoot = 'C:\opt\quant'
$DeskRoot = Join-Path $RepoRoot 'desks\mt5'
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
function Reg($name, $action, $trigger, $settings, $desc) {
    try {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
            -Settings $settings -Principal $principal -Description $desc | Out-Null
        Write-Host ("  [OK  ] {0} registered" -f $name)
    } catch { Write-Host ("  [FAIL] {0} {1}" -f $name, $_.Exception.Message) }
}
$ps = (Get-Command powershell.exe).Source
$base = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 10)

# --- the two desk-cycle lanes: -Once with a repetition, the shape PS 5.1 accepts (the -Daily
# parameter set rejects -RepetitionInterval, which is why both lanes were silently absent).
$noonA = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $RepoRoot -Argument `
    ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}\scripts\Run-DeskCycle.ps1" -Lane noon' -f $DeskRoot)
$noonT = New-ScheduledTaskTrigger -Once -At ([datetime]::Today.AddHours(12)) `
    -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 11)
Reg "MT5-CycleNoon" $noonA $noonT $base "Daily wiring pass (noon lane): schedule the unwired, repair staleness and failing tasks."

$midA = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $RepoRoot -Argument `
    ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}\scripts\Run-DeskCycle.ps1" -Lane midnight' -f $DeskRoot)
$midT = New-ScheduledTaskTrigger -Once -At ([datetime]::Today) `
    -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 11)
Reg "MT5-CycleMidnight" $midA $midT $base "Daily wiring pass (midnight lane): schedule the unwired, repair staleness and failing tasks."

# --- the post-reboot drill, read-only apart from re-enabling a task Windows left Disabled.
$drillA = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $RepoRoot -Argument `
    ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}\ops\reboot_drill.ps1"' -f $RepoRoot)
$drillT = New-ScheduledTaskTrigger -Daily -At "06:30"
$drillS = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Reg "MT5-RebootDrill" $drillA $drillT $drillS "Daily post-reboot drill: terminal, required tasks and account freshness; records PASS/FAIL for the issue board."

# --- the 15-minute shadow-health publisher, five minutes off the replay slots.
$syncA = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $RepoRoot -Argument `
    ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}\scripts\sync_shadow_to_git.ps1"' -f $DeskRoot)
$syncT = New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(5)) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
$syncS = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Reg "MT5-ShadowSync" $syncA $syncT $syncS "Commit MT5 shadow-health state to git for cross-brain visibility."
