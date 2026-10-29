# REGISTER Quant-BoxSelfHeal -- THE CLOSED SELF-HEAL TABLE, EVERY FIVE MINUTES, AS SYSTEM (2026-10-29).
#
# THE PASTE IT RETIRES. zuck had to open an admin PowerShell and, by hand: stop a wedged
# merge_hypotheses that held data\.job_locks\merge_hypotheses.json, stop a pf_allocator heavy pass
# that held the allocator lock past its budget, stop the gate's gh "pulls" child and python,
# `schtasks /end` a hung MT5-IndependenceIntake, `schtasks /end` + `/run` a Quant-WorkflowGate that
# had been dead since a crash, and add the gate repo to git's safe.directory. ops\box_self_heal.py
# is the SYSTEM-only lines of that paste (end the hung task, end a wedged gate tree, restart a dead
# gate) as a fixed, reviewed rule table with the evidence each one needs before it fires (past
# budget AND dead owner or no CPU progress across two passes); this registers its clock. The two
# job-lock lines are job_lock's own wedged-owner stop (#526, scripts/check_job_locks.py), not this.
#
# WHY SYSTEM. The gate and the tasks it clears run elevated or as SYSTEM. The bridge and every
# cloud session are non-elevated, and a non-elevated process can neither stop an elevated one nor
# `schtasks /End` a SYSTEM task -- which is the only reason the paste needed zuck at all. A
# watchdog that ran with less would log "access denied" every five minutes and clear nothing.
#
# THE ONE-TIME MACHINE CONFIG. The paste's `git config --global --add safe.directory` line is
# written here instead, ONCE, to the SYSTEM git config (not --global: SYSTEM's HOME is
# systemprofile, so a --global entry written from an admin shell lands in the wrong file -- the
# install_adopt_release_task.ps1 lesson). workflow_gate.ps1 also passes it at command scope, so
# this is belt and braces for any other git call into the gate clone. Idempotent.
#
# IDEMPOTENT. With -IfMissing it does nothing when the task already exists (the form
# Adopt-And-Seal.ps1's ensure-task list calls). Without it, it replaces the registration with
# exactly this one.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_box_self_heal_task.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_box_self_heal_task.ps1 -IfMissing
param([switch]$IfMissing)

$ErrorActionPreference = 'Stop'

$TaskName = 'Quant-BoxSelfHeal'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Script   = Join-Path $RepoRoot 'ops\box_self_heal.py'
if (-not (Test-Path $Script)) { throw "box_self_heal.py missing at $Script" }

if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0}: already registered; -IfMissing leaves it exactly as it is" -f $TaskName
    exit 0
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "run this elevated: registering a SYSTEM task needs an administrator" }

$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python.exe -ErrorAction Stop).Source
}
& $Python -c "import psutil" 2>$null
if ($LASTEXITCODE -ne 0) {
    "WARNING: psutil is not importable by $Python; the watchdog will report UNMEASURED (RED) and stop nothing until it is"
}
$LogDir = Join-Path $DeskRoot 'logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$Log = Join-Path $LogDir 'Quant-BoxSelfHeal.log'

# No arguments: the rule table is in the code, and the only flag it has is --dry-run.
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -WorkingDirectory $RepoRoot -Argument `
    ('/d /s /c ""{0}" -W ignore "{1}" >> "{2}" 2>&1"' -f $Python, $Script, $Log)

# A DAILY trigger repeating every five minutes for one day, never a long -Once (one expired on
# this box 2026-09-21 with Next Run Time N/A). Offset to :03 so it misses the :05/:12/:20 writers.
$at = (Get-Date).Date.AddMinutes(3)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $at `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# Four minutes: a pass is two schtasks queries and one process scan. A pass that takes longer is
# itself the defect, and the report going stale is how desk health shows it (RED past 20 min).
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$gateRepo = 'C:/ProgramData/QuantBox/gate-repo'
$already = @(git config --system --get-all safe.directory 2>$null)
if ($already -notcontains $gateRepo) {
    git config --system --add safe.directory $gateRepo 2>&1 | Out-Null
    "safe.directory: added {0} to the SYSTEM git config" -f $gateRepo
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Closed self-heal table (ops\box_self_heal.py): a hung MT5-IndependenceIntake, a wedged or dead Quant-WorkflowGate only; never the terminal, the money path, the bridge or the miners. Every act and refusal is RED in reports\BOX_SELF_HEAL.json." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} user={2} interval={3}" -f $t.TaskName, $t.State, $t.Principal.UserId, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 20
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"report: desks\mt5\reports\BOX_SELF_HEAL.json; ledger: desks\mt5\logs\box_self_heal.jsonl; log: {0}" -f $Log
