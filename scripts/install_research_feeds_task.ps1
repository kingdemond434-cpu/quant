# REGISTER Quant-ResearchFeeds -- THE PAPER / WORKING-PAPER CLOCK, ON THE BOX (2026-11-25).
#
# THE GAP. seed_miners' research_feeds (central-bank and NBER working papers), arxiv_qfin and
# bis_speeches were clocked only by the VPS timer quant-seed-miners.timer (retired for this desk);
# on the box they ran solely as a rotating beat of the heavy-plan scout_swarm leg. This registers
# `seed_miners.py --only research_feeds,arxiv_qfin,bis_speeches` every 6 hours at :55, SYSTEM,
# IgnoreNew, 40-minute watchdog. Idempotent with -IfMissing.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_research_feeds_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'Quant-ResearchFeeds'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Runner   = Join-Path $RepoRoot 'ops\run_research_feeds.cmd'
if (-not (Test-Path $Runner)) { throw "run_research_feeds.cmd missing at $Runner" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "{0}"' -f $Runner) `
    -WorkingDirectory $RepoRoot

$now = Get-Date
$start = $now.Date.AddHours($now.Hour).AddMinutes(55)
if ($start -le $now) { $start = $start.AddHours(1) }
$trigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Hours 6)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Paper feeds: working papers, arXiv q-fin, BIS speeches, every 6 hours; research only." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} first={2:HH:mm} every 6h runs={3}" -f $t.TaskName, $t.State, $start, $Runner
