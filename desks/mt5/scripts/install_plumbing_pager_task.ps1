# REGISTER THE PLUMBING PAGER, AND RUN IT NOW (audit HOLD on 018de05c5 / beb36218, 2026-10-20).
#
# WHY THE BOX PAGES ITSELF. scripts/run_alerts.py, the desk's pager, ran only from the VPS cron,
# and the VPS runs the orphan desk-sync-clean, which never receives what this pager reads:
# desks/mt5/reports/PLUMBING_WATCHDOG.json (box-local, gitignored), docs/research/PLUMBING_ALERTS.md
# and desks/mt5/reports/JUDGING_RATE.json. So the box runs `run_alerts.py --box` from its own
# files: CRITICAL plumbing rows, a stalled judge (no new verdict in JUDGE_STALL_H), UNMEASURED
# inputs, each re-paged every REPAGE_H while still failing, through the existing ntfy sender.
#
# EXIT CODES ARE THE ALARM FOR THE ALARM. 0 = every due page went out; 2 = NOT ARMED (no readable
# ntfy topic: nothing sent, no topic created); 3 = a due page was not delivered. A pager cannot
# page about itself, so MT5-PlumbingWatchdog reads this task's LAST RESULT every 15 minutes and
# raises any non-zero one as a `pager_task` defect (desk state, events log, PLUMBING_ALERTS.md).
#
# THE PRINCIPAL. The installing user, Interactive, RunLevel LIMITED -- exactly as MT5-ShadowSync is
# registered (Install-QuantWindows.ps1). The pager needs no elevation: it reads three reports and
# one secret and writes desks\mt5\logs and data\.pager_backoff. It never touches MetaTrader.
#
# THE SECRET. The ntfy topic lives in data\secrets\ntfy.json, the same file the VPS pager uses.
# COPY that file onto the box (never retype it, never put it in the repo), or pass it here with
# -SecretFrom <path>: the file is read (any encoding PowerShell detects, UTF-16 included),
# validated, and rewritten as UTF-8 without a BOM -- PS 5.1's Out-File writes UTF-16, which the
# pager would read as NOT ARMED. The topic is never echoed.
#
# THE TRIGGER SHAPE copies install_plumbing_watchdog_task.ps1: a DAILY trigger repeating every
# 15 minutes for one day (a -Once trigger with a long duration expired on this box and stopped
# adoption for four days). Offset to :10, three minutes after the watchdog's :07.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File desks\mt5\scripts\install_plumbing_pager_task.ps1 [-SecretFrom C:\path\ntfy.json]

param([string]$SecretFrom = '')

$ErrorActionPreference = 'Stop'

$TaskName = 'MT5-PlumbingPager'
$DeskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot '..\..')).Path
$Script   = Join-Path $RepoRoot 'scripts\run_alerts.py'
if (-not (Test-Path $Script)) { throw "run_alerts.py missing at $Script" }

if ($SecretFrom) {
    $raw = Get-Content -Raw -LiteralPath $SecretFrom
    $doc = $raw | ConvertFrom-Json
    if (-not ($doc.topic -is [string]) -or -not $doc.topic.Trim()) {
        throw "-SecretFrom $SecretFrom carries no 'topic' string; nothing written"
    }
    $dest = Join-Path $RepoRoot 'data\secrets\ntfy.json'
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    $json = (@{ topic = $doc.topic.Trim() } | ConvertTo-Json -Compress)
    [System.IO.File]::WriteAllText($dest, $json, (New-Object System.Text.UTF8Encoding($false)))
    Remove-Variable raw, doc, json
    "secret written to data\secrets\ntfy.json (UTF-8, no BOM; value not shown)"
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = 'python' }

$action = New-ScheduledTaskAction -Execute $python -Argument `
    ("-W ignore `"{0}`" --box" -f $Script) -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date.AddMinutes(10))
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date.AddMinutes(10)) `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# IgnoreNew: a hung push never stacks a second pass. Five minutes bounds a dead network
# (each push is 15 s at most).
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel Limited

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings `
    -Description "Page the principal every 15 minutes on CRITICAL plumbing defects, a stalled judge, and UNMEASURED plumbing/judge inputs (scripts/run_alerts.py --box)." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} interval={2} user={3} runlevel={4}" -f $t.TaskName, $t.State, `
    $t.Triggers[0].Repetition.Interval, $t.Principal.UserId, $t.Principal.RunLevel

# Run it now and WAIT for the real result: 267009 is "still running" and 267011 "not yet run";
# neither is an answer, and reading one after a fixed sleep reported a pass that had not ended.
Start-ScheduledTask -TaskName $TaskName
$deadline = (Get-Date).AddMinutes(6)
do {
    Start-Sleep -Seconds 3
    $i = Get-ScheduledTaskInfo -TaskName $TaskName
    $running = (Get-ScheduledTask -TaskName $TaskName).State -eq 'Running'
} while (($running -or $i.LastTaskResult -in 267009, 267011) -and (Get-Date) -lt $deadline)

$rc = [int]$i.LastTaskResult
"first pass {0}: last_run={1} last_result={2}" -f $TaskName, $i.LastRunTime, $rc
"dedupe state: desks\mt5\logs\plumbing_pager_state.json"
if ($rc -eq 0) { "ARMED: every due page went out"; exit 0 }
if ($rc -eq 2) {
    "NOT ARMED: no readable ntfy topic -- copy data\secrets\ntfy.json onto the box (or re-run with -SecretFrom <path>). Nothing was paged."
    exit 2
}
if ($rc -in 267009, 267011) { "UNMEASURED: the first pass did not finish within 6 minutes"; exit 1 }
"FAILED: the first pass exited $rc -- a due page was not delivered; read desks\mt5\logs and data\alert_delivery.jsonl"
exit $rc
