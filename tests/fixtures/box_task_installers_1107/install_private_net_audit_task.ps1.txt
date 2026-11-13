# REGISTER MT5-PrivateNetAudit -- THE DAILY MANAGEMENT-PORT AUDIT (2026-11-13).
#
# THE GAP. `desks/mt5/ops/box_tasks.manifest` declared MT5-PrivateNetAudit on 2026-09-30
# ("daily at 06:40", runs desks/mt5/scripts/install_private_net.ps1, lane=ops) with
# `installer="NONE"`. install_private_net.ps1's own header says "MT5-PrivateNetAudit runs it
# daily" and the manifest's comment says "Register: the same script with no switch, daily" --
# and nothing in the repository ever did the registering, so data\private_net.json (EXPOSED /
# PRIVATE / UNMEASURED) was written only when someone ran the script by hand.
#
# WHAT IT REGISTERS, every value read off the manifest or the script:
#   trigger    daily at 06:40 box-local (the manifest's line). A daily trigger re-arms itself and
#              has no repetition duration to expire (install_frontier_audit_task.ps1).
#   action     powershell.exe -File install_private_net.ps1 with NO SWITCH -- AUDIT mode, which
#              reads the inbound 22/3389 rules and Tailscale's state and writes
#              desks\mt5\data\private_net.json. It changes nothing.
#   principal  SYSTEM, ServiceAccount: Get-NetFirewallRule needs an elevated token and the audit
#              needs no user profile. The same principal shape as MT5-FrontierAudit.
#
# -Enforce, -Confirm AND -Rollback ARE NEVER SCHEDULED, and this installer cannot pass them: the
# argument line below is fixed. Enforcement is an operator's act with a 15-minute dead-man
# rollback, run by hand (install_private_net.ps1's header).
#
# IDEMPOTENT. Without switches it replaces any existing registration with exactly this one. With
# -IfMissing it does nothing when the task exists (the Adopt-And-Seal.ps1 ensure-task form).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_private_net_audit_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_private_net_audit_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-PrivateNetAudit'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Audit    = Join-Path $DeskRoot 'scripts\install_private_net.ps1'
$Log      = Join-Path $DeskRoot ('logs\{0}.log' -f $TaskName)
if (-not (Test-Path $Audit)) { throw "install_private_net.ps1 missing at $Audit" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Log) | Out-Null

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$ps = (Get-Command powershell.exe).Source
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $RepoRoot -Argument (
    '/d /s /c ""{0}" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{1}" >> "{2}" 2>&1"' -f $ps, $Audit, $Log)

# Daily at 06:40 (the cadence box_tasks.manifest declares).
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddHours(6).AddMinutes(40))

# StartWhenAvailable: an 06:40 missed to a reboot is caught up rather than skipped a whole day.
# Fifteen minutes is a watchdog on a hung tailscale.exe call, not a budget: the audit reads a
# handful of firewall rules and returns in seconds.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Private-network AUDIT, daily: install_private_net.ps1 with no switch writes data\private_net.json and changes nothing. -Enforce is never scheduled.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} next={2} runs={3} (audit mode)" -f $t.TaskName, $t.State, $i.NextRunTime, $Audit
if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
    Write-Host ("FATAL: {0} registered with no next run time" -f $TaskName)
    exit 4
}
