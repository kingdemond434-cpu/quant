# Register MT5-PrivateNetAudit: the daily, read-only exposure audit of SSH (22) and RDP (3389).
#
# Runs install_private_net.ps1 with NO switch, which only reads the firewall and Tailscale state
# and writes desks\mt5\data\private_net.json (EXPOSED / PRIVATE / UNMEASURED). It changes nothing.
# -Enforce is never scheduled: it is an operator act with its own 15-minute dead-man rollback.

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
  '-NoProfile -ExecutionPolicy Bypass -File C:\opt\quant\desks\mt5\scripts\install_private_net.ps1')

$trigger = New-ScheduledTaskTrigger -Daily -At '06:40'

$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -StartWhenAvailable

Register-ScheduledTask -TaskName 'MT5-PrivateNetAudit' -Action $action -Trigger $trigger `
  -Settings $settings -User 'SYSTEM' -RunLevel Highest -Force | Out-Null

$t = Get-ScheduledTask -TaskName 'MT5-PrivateNetAudit'
Write-Output ("MT5-PrivateNetAudit registered: " + $t.State)
