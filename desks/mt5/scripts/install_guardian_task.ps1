<#
.SYNOPSIS
    Register MT5-Guardian on the trading box. Idempotent; touches only this one task.

.DESCRIPTION
    ops\run_guardian.cmd every 15 minutes as SYSTEM (highest privileges), independent of the
    hourly cycle, so a hung cycle can no longer take the guardian down with it:
      1. ops\alert_feed.py reads every box page back off the ntfy topic into
         desks\mt5\reports\alerts\CLAUDE_ALERT_FEED.jsonl, where Claude reads it.
      2. desks\mt5\research\run_desk_self_heal.py --apply acts on process_health.json: bounded
         End+Run of faulted NON-money tasks, a page for everything else. The money path, the
         release/sign/forge chain and the bridge are never re-run or ended (board_rerunnable).
    Revert: Disable-ScheduledTask -TaskName MT5-Guardian (the hourly self-heal leg keeps running).

        powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_guardian_task.ps1 [-IfMissing]
#>
[CmdletBinding()]
# -IfMissing: register only when the task does not exist, and touch nothing otherwise. This is the
# form Adopt-And-Seal calls on every adoption (step 1b), so the guardian appears on the box by itself
# and nobody ever pastes this installer (principal 2026-11-25 11:53Z).
param([string] $RepoRoot = "C:\opt\quant", [switch]$IfMissing)
$ErrorActionPreference = "Stop"

$TaskName = "MT5-Guardian"
if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}
$cmd = Join-Path $RepoRoot "ops\run_guardian.cmd"
if (-not (Test-Path $cmd)) { throw "run_guardian.cmd missing at $cmd" }

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$cmd`"" -WorkingDirectory $RepoRoot
# A DAILY trigger repeating for one day re-arms itself at midnight and never expires.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(2))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(2)) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 12) `
    -MultipleInstances IgnoreNew -Priority 6

$why = "Box guardian: alert feed to Claude + bounded self-heal off the process board (never the money path)"
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings | Out-Null
    Write-Host "  updated $TaskName"
} else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $why | Out-Null
    Write-Host "  created $TaskName"
}
Start-ScheduledTask -TaskName $TaskName
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table -AutoSize
