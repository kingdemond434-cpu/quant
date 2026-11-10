# REGISTER Quant-SideChannelMiners -- THE 25 EXTERNAL DISCOVERY CHANNELS, ON THE BOX (2026-11-05).
#
# THE GAP. desks/mt5/side_channels/run_all_miners.py had no caller on the box: it ran only from
# the Linux VPS chain (ops/run_daily_brain_chain.sh via scripts/run_miners_fallback.py). That
# chain's intel-ship stopped on 2026-11-03, and on 2026-11-05 nineteen miner seats went DEAD
# together in PRODUCER_YIELD. This registers the suite on the box, every two hours, so the seats
# run 24/7 next to the compiler that reads them.
#
# WHAT IT DOES. Registers Quant-SideChannelMiners as `cmd.exe /c ops\run_side_channel_miners.cmd`,
# SYSTEM, every 2 hours starting at the next :45 (clear of the :05/:12/:20 repository-writer
# slots). 25 channels at a 180 s per-channel kill is at most 75 minutes; the 110-minute limit is a
# watchdog, and IgnoreNew means a slow pass is never doubled.
#
# IDEMPOTENT. -IfMissing does nothing when the task exists, so it is safe to call from any
# ensure step or by hand; a registered task is never touched.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_side_channel_miners_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_side_channel_miners_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'Quant-SideChannelMiners'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Runner   = Join-Path $RepoRoot 'ops\run_side_channel_miners.cmd'
if (-not (Test-Path $Runner)) { throw "run_side_channel_miners.cmd missing at $Runner" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "{0}"' -f $Runner) `
    -WorkingDirectory $RepoRoot

$now = Get-Date
$start = $now.Date.AddHours($now.Hour).AddMinutes(45)
if ($start -le $now) { $start = $start.AddHours(1) }
$trigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Hours 2)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 110) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Side-channel miner suite (25 external discovery channels), every 2 hours; research only." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} first={2:HH:mm} every 2h runs={3}" -f $t.TaskName, $t.State, $start, $Runner
