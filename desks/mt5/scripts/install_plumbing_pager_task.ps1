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
# ntfy topic: no topic created; the independent channels are still tried); 3 = a due page was not
# delivered. A pager cannot page about itself, so every pass writes
# desks\mt5\reports\PLUMBING_PAGER.json {at, rc, due, sent} (MT5-BoxHeartbeat's `pager` check
# reads it once that check lands -- deliberately AFTER this installer has printed S4U/Limited and
# ARMED), and MT5-PlumbingWatchdog raises a `pager_task` defect when the task's last result is
# non-zero or unreadable, or it has not fired in 45 min.
#
# THE PRINCIPAL. The installing user at RunLevel LIMITED, logon type S4U FIRST: it runs with nobody
# logged on (a reboot without autologon leaves no session, and an Interactive task then never
# fires), stores no password, and its lack of network credentials does not matter for HTTPS.
# Registering S4U needs an elevated prompt; if it fails, this falls back to Interactive/Limited --
# MT5-ShadowSync's shape (Install-QuantWindows.ps1) -- and SAYS SO, because that task fires only
# while the user holds a session. The pager needs no elevation at run time: it reads three reports
# and one secret and writes desks\mt5\logs, desks\mt5\reports and data\.pager_backoff. It never
# touches MetaTrader.
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
    # a parse error message can quote the input: never let it reach the console
    try { $doc = $raw | ConvertFrom-Json } catch { $doc = $null }
    if ($null -eq $doc) {
        Remove-Variable raw
        throw "-SecretFrom: the file is not valid JSON (content not shown); nothing written"
    }
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
    -RepetitionDuration (New-TimeSpan -Hours 25)).Repetition
# 25 h, not 1 day: on the autumn DST day the wall-clock day is 25 h long, and a 24 h repetition
# would leave an hour with no pass (longer than the 45 min every reader allows). The overlap on
# the other days only re-fires a pass that IgnoreNew already absorbs.

# IgnoreNew: a hung push never stacks a second pass. Five minutes bounds a dead network
# (each push is 15 s at most).
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$desc = "Page the principal every 15 minutes on CRITICAL plumbing defects, a stalled judge, and UNMEASURED plumbing/judge inputs (scripts/run_alerts.py --box)."
try {
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $desc | Out-Null
    $registeredAs = 'S4U/Limited (runs with nobody logged on)'
} catch {
    "S4U registration failed ({0}); falling back to Interactive/Limited" -f $_.Exception.GetType().Name
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
        -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Description $desc | Out-Null
    $registeredAs = 'Interactive/Limited (fires ONLY while this user holds a session; re-run elevated for S4U)'
}
"intended {0}" -f $registeredAs

# READ BACK what the scheduler actually holds: the branch taken is an intention, not a fact.
$t = Get-ScheduledTask -TaskName $TaskName
"registered {0} as {1}/{2} (scheduler read-back): user={3} state={4} interval={5}" -f `
    $t.TaskName, $t.Principal.LogonType, $t.Principal.RunLevel, $t.Principal.UserId, $t.State, `
    $t.Triggers[0].Repetition.Interval
if ("$($t.Principal.LogonType)" -ne 'S4U') {
    "WARNING: not S4U -- the pager fires only while $($t.Principal.UserId) holds a session. Do NOT land the heartbeat pager check until this reads S4U/Limited."
}

# The scheduler's RegistrationInfo date is often empty; the watchdog excuses "has not yet run"
# (267011) only inside 45 min of a registration time, so record one it can read.
$stamp = Join-Path $DeskRoot 'logs\plumbing_pager_installed.json'
New-Item -ItemType Directory -Force -Path (Split-Path $stamp) | Out-Null
[System.IO.File]::WriteAllText($stamp, ('{{"at": "{0}"}}' -f `
    (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')), `
    (New-Object System.Text.UTF8Encoding($false)))

# Run it now and WAIT for the real result: 267009 is "still running" and 267011 "not yet run";
# neither is an answer, and reading one after a fixed sleep reported a pass that had not ended.
Start-ScheduledTask -TaskName $TaskName
$deadline = (Get-Date).AddMinutes(6)
do {
    Start-Sleep -Seconds 3
    $i = Get-ScheduledTaskInfo -TaskName $TaskName
    $running = (Get-ScheduledTask -TaskName $TaskName).State -eq 'Running'
} while (($running -or $i.LastTaskResult -in 267009, 267011) -and (Get-Date) -lt $deadline)

# [int64]: an HRESULT above 0x7FFFFFFF (0x80070002, python missing) overflows [int]
$rc = [int64]$i.LastTaskResult
"first pass {0}: last_run={1} last_result={2}" -f $TaskName, $i.LastRunTime, $rc
"dedupe state: desks\mt5\logs\plumbing_pager_state.json"
if ($rc -eq 0) { "ARMED: every due page went out"; exit 0 }
if ($rc -eq 2) {
    "NOT ARMED: no readable ntfy topic -- copy data\secrets\ntfy.json onto the box (or re-run with -SecretFrom <path>). Nothing was paged."
    exit 2
}
if ($rc -in 267009, 267011) { "UNMEASURED: the first pass did not finish within 6 minutes"; exit 1 }
"FAILED: the first pass exited $rc -- a due page was not delivered; read desks\mt5\logs and data\alert_delivery.jsonl"
if ($rc -ge 1 -and $rc -le 255) { exit [int]$rc }
exit 1
