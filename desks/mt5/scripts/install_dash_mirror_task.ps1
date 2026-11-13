# REGISTER MT5-DashMirror -- THE DASHBOARD INPUT MIRROR, EVERY 3 MINUTES (2026-11-13).
#
# THE GAP. scripts\check_scheduled_tasks.py records MT5-DashMirror as one of the only two tasks
# Get-ScheduledTask returned on 2026-09-15, and `desks/mt5/ops/box_tasks.manifest` declared it
# `trigger="UNDECLARED" runs="UNKNOWN" installer="NONE"`. Its runner, ops\dash_mirror.cmd, writes
# logs\dash_mirror.log and is the only file in this repository that does what the name says.
#
# WHERE EVERY VALUE COMES FROM:
#   runs       ops\dash_mirror.cmd: scp's the board's input artifacts (shadow health, gateway and
#              account state, sleeves, the allocator's book, the survivors, the ledger) so the VPS's
#              existing pull regenerates a current board.
#   cadence    EVERY 3 MINUTES: the runner's own backoff comment sizes its retries against "a
#              3-minute clock" ("costs at most 35 seconds on a 3-minute clock").
#   principal  -RunAs (default: the account running this installer), LogonType S4U -- headless,
#              survives logoff, no password stored; the same pattern as install_cro_cycle_tasks.ps1.
#              NOT SYSTEM: the runner authenticates with %USERPROFILE%\.ssh\id_ed25519, and under
#              SYSTEM %USERPROFILE% is the system profile, which holds no key, so every copy would
#              fail and be counted STALE AFTER COPY. This installer refuses SYSTEM for that reason.
#
# NO SECRET AND NO ADDRESS IS WRITTEN HERE. The runner reads the trading box's host from the
# machine environment variable QUANT_BOX_HOST (never committed; tests/ops/
# test_live_infrastructure_is_not_published.py fences it) and refuses with exit 2 when it is
# absent. This installer only WARNS when it is unset, so the registration still lands and the
# refusal shows up in LastTaskResult and the log rather than nowhere.
#
# IT IS A BRIDGE, on the runner's own terms: "The moment the VPS is repointed at the trading box
# directly, delete this task and this file." Registering it does not change that.
#
# IDEMPOTENT. Without -IfMissing it replaces any existing registration with exactly this one. With
# -IfMissing it does nothing when the task exists (the Adopt-And-Seal.ps1 ensure-task form).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_dash_mirror_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_dash_mirror_task.ps1 -RunAs BOX\Administrator
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_dash_mirror_task.ps1 -IfMissing
param(
    [switch] $IfMissing,
    [string] $RunAs = ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME)
)

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-DashMirror'

if ($RunAs -match '^(NT AUTHORITY\\)?(SYSTEM|LOCAL SYSTEM)$' -or $RunAs -match '\\\$?SYSTEM$' -or $RunAs -eq 'S-1-5-18') {
    throw "RunAs '$RunAs' is SYSTEM: the mirror's ssh key lives in a user profile. Pass -RunAs <the account whose profile holds .ssh\id_ed25519>."
}

$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Runner   = Join-Path $RepoRoot 'ops\dash_mirror.cmd'
if (-not (Test-Path $Runner)) { throw "dash_mirror.cmd missing at $Runner" }
New-Item -ItemType Directory -Force -Path (Join-Path $DeskRoot 'logs') | Out-Null

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; nothing to do" -f $TaskName
    exit 0
}

if (-not [Environment]::GetEnvironmentVariable('QUANT_BOX_HOST', 'Machine')) {
    Write-Warning 'QUANT_BOX_HOST is not set in the machine environment: the mirror will refuse (exit 2) until it is.'
}

$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/c "{0}"' -f $Runner) `
    -WorkingDirectory $RepoRoot

# Every 3 minutes, forever: a -Daily trigger whose Repetition is copied from a -Once trigger
# (install_cro_cycle_tasks.ps1). A -Once repetition ends when its duration ends, and PowerShell
# 5.1's -Daily set rejects -RepetitionInterval.
$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date)
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 3) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# IgnoreNew: a pass slowed by the runner's backoff (up to 35 s per file) never stacks a second
# copy on the same files. Ten minutes is a watchdog on a hung scp, not a budget.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $RunAs -LogonType S4U -RunLevel Highest

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description 'Dashboard input mirror, every 3 minutes: ops\dash_mirror.cmd copies the board inputs; a bridge until the VPS reads the trading box directly.' | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0}: state={1} runas={2} logon={3} every={4} next={5}" -f $t.TaskName, $t.State,
    $t.Principal.UserId, $t.Principal.LogonType, $t.Triggers[0].Repetition.Interval, $i.NextRunTime
if (-not $i.NextRunTime -or $i.NextRunTime.Year -lt 2000) {
    Write-Host ("FATAL: {0} registered with no next run time" -f $TaskName)
    exit 4
}
