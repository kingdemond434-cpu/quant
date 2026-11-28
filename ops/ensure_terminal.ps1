$ErrorActionPreference = 'Stop'

$exe = 'C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe'
$root = 'C:\opt\quant'
$log = Join-Path $root 'desks\mt5\logs\MT5-TerminalBoot.log'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'
$session = (Get-Process -Id $PID).SessionId

# A PID is not proof of a usable terminal. On 2026-10-02 the sole Fusion
# process was windowless in Session 0 while every MT5 API call timed out.
# Never launch a GUI terminal from that non-interactive session.
if ($session -eq 0) {
    Add-Content -LiteralPath $log -Value "$stamp watchdog in Session 0; refusing a headless launch or false health verdict"
    exit 2
}

# Get-Process, never the CIM cmdlets: CIM has hung on the trading box (CLAUDE.md), and a
# watchdog that hangs is no watchdog. A terminal64 whose Path this account cannot read belongs
# to another account; it is NOT ours (counting it made any foreign MT5 refuse forever), so it is
# logged by session and left out.
function Get-FusionTerminals {
    @(Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $exe })
}
foreach ($u in @(Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue |
        Where-Object { -not $_.Path })) {
    Add-Content -LiteralPath $log -Value "$stamp unreadable-path terminal in session $($u.SessionId) (pid $($u.Id)); not counted as Fusion"
}
$terminals = Get-FusionTerminals
$local = @($terminals | Where-Object { $_.SessionId -eq $session })
# An unreadable terminal in THIS session is not another account's: it may be the Fusion terminal
# itself behind an access hiccup. Launching beside it would make two terminals on one data
# directory, so its presence refuses the launch below.
$unreadableLocal = @(Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue |
    Where-Object { -not $_.Path -and $_.SessionId -eq $session })

# A SESSION-0 FUSION TERMINAL IS NEVER THE DESK'S TERMINAL, AND IS CLOSED HERE (2026-11-17).
# After the 11-12 and 11-16 reboots a SYSTEM task's bare initialize() started terminal64 headless
# in Session 0 with no login. Nothing can use it: it has no desktop to log in on, no reader may
# attach to it (test_system_tasks_never_launch_session0_terminal), and this watchdog refused to
# launch beside it -- so the feed sat dark until the principal closed it by hand, twice. The
# principal's standing order is that a reboot needs nobody. So: from an INTERACTIVE session only
# (Session 0 exited above), every terminal64 whose Path is EXACTLY the Fusion executable and
# whose SessionId is 0 is closed, journalled to this log and to the event log, and the census is
# re-read. Closing a terminal closes no position (positions live on the broker's server). A
# terminal in any OTHER interactive session, or another broker's terminal, is never touched: the
# refusals below still hold for those.
$headless = @($terminals | Where-Object { $_.SessionId -eq 0 })
if ($headless.Count -gt 0) {
    $events = Join-Path $root 'desks\mt5\data\events.jsonl'
    foreach ($h in $headless) {
        $closed = $true
        try { Stop-Process -Id $h.Id -Force -ErrorAction Stop } catch { $closed = $false }
        $verdict = if ($closed) { 'closed' } else { 'close FAILED' }
        Add-Content -LiteralPath $log -Value "$stamp JOURNAL headless Session 0 Fusion terminal pid $($h.Id) $verdict from session $session; re-reading the census"
        $row = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss+00:00');
                           kind = 'TERMINAL_SESSION0_CLOSED'; producer = 'MT5-TerminalBoot';
                           host = $env:COMPUTERNAME; pid = $h.Id; watchdog_session = $session;
                           closed = $closed; ack_state = 'UNACKNOWLEDGED' }
        try {
            Add-Content -LiteralPath $events -Value ($row | ConvertTo-Json -Compress) -Encoding UTF8
        } catch {
            Add-Content -LiteralPath $log -Value "$stamp event log not written: $($_.Exception.GetType().Name)"
        }
    }
    Start-Sleep -Seconds 3
    $terminals = Get-FusionTerminals
    $local = @($terminals | Where-Object { $_.SessionId -eq $session })
}

# A terminal in another session may own live state. Refuse to kill it or launch
# another on the same data directory without controlled reconciliation.
if ($terminals.Count -gt 0 -and $local.Count -eq 0) {
    $sessions = ($terminals | ForEach-Object { $_.SessionId }) -join ','
    Add-Content -LiteralPath $log -Value "$stamp terminal in session(s) $sessions, watchdog in $session; IPC unverified, controlled recovery required"
    exit 2
}
if ($local.Count -gt 1) {
    Add-Content -LiteralPath $log -Value "$stamp $($local.Count) Fusion terminals in session $session; refusing to guess which owns live state"
    exit 2
}
if ($terminals.Count -gt 1) {
    Add-Content -LiteralPath $log -Value "$stamp Fusion terminals span sessions; refusing automatic termination of an unverified owner"
    exit 2
}

# The existing probe uses MT5 initialize/account_info only; no order permission.
# THE INTERPRETER IS RESOLVED, NEVER ASSUMED: a hard-coded path that is absent on this box reads
# "probe unavailable" forever and the watchdog can never pass. Order: the repo .venv, the per-user
# Python314 (Seal-IfClean.ps1's two candidates), then the machine-wide Program Files Python314
# (the path this script used to hard-code), then whatever `python` is on PATH.
$python = $null
foreach ($cand in @(
    (Join-Path $root '.venv\Scripts\python.exe'),
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
    'C:\Program Files\Python314\python.exe'
)) { if (Test-Path -LiteralPath $cand) { $python = $cand; break } }
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
}
$probe = Join-Path $root 'desks\mt5\research\probe_terminal.py'

# One read-only probe, used on both paths below. Returns the probe's exit code (99 = unavailable).
function Invoke-ReadOnlyProbe {
    if (-not $python -or -not (Test-Path -LiteralPath $probe)) {
        Add-Content -LiteralPath $log -Value "$stamp read-only Fusion IPC probe unavailable"
        return 99
    }
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue' # native stderr is data; the exit code is the verdict
    try {
        $probeOutput = & $python -u $probe 2>&1 | Out-String
        $probeCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorAction
    }
    if ($probeCode -ne 0) {
        $reason = ($probeOutput -split "`n" | Where-Object { $_ -match 'init:|last_error|Traceback|Error' } | Select-Object -First 1)
        Add-Content -LiteralPath $log -Value "$stamp Fusion IPC/account probe failed rc=$probeCode session=$session $reason"
    }
    return $probeCode
}

# THE HEALTH FILE IS WRITTEN ON A PASSED PROBE ONLY. Every refusal appends to the log, so the
# log's age says the task ran, not that the terminal is usable; organ_contract grades this file.
function Write-BootHealth([int]$terminalPid, [string]$note) {
    Add-Content -LiteralPath $log -Value "$stamp Fusion IPC/account probe passed in session $session (pid $terminalPid)$note"
    $okPath = Join-Path $root 'desks\mt5\data\terminal_boot_ok.json'
    @{ at = (Get-Date).ToUniversalTime().ToString('o'); session = $session; pid = $terminalPid;
       python = $python } | ConvertTo-Json -Compress | Set-Content -LiteralPath $okPath -Encoding UTF8
}

# An unreadable terminal in THIS session may be the Fusion terminal itself: never launch beside
# it. Ask the read-only probe first -- if the terminal answers, it is healthy and that is the
# verdict; only an unanswering one is refused.
if ($local.Count -eq 0 -and $unreadableLocal.Count -gt 0) {
    $pids = ($unreadableLocal | ForEach-Object { $_.Id }) -join ','
    if ((Invoke-ReadOnlyProbe) -eq 0) {
        Write-BootHealth $unreadableLocal[0].Id " (unreadable-path terminal(s) $pids; no launch)"
        exit 0
    }
    Add-Content -LiteralPath $log -Value "$stamp unreadable-path terminal(s) $pids in this session $session; refusing to launch a second terminal"
    exit 2
}
if ($local.Count -eq 0) {
    if (-not (Test-Path -LiteralPath $exe)) {
        Add-Content -LiteralPath $log -Value "$stamp Fusion terminal executable missing: $exe"
        exit 2
    }
    Start-Process -FilePath $exe -WindowStyle Hidden
    Start-Sleep -Seconds 8
    $local = @(Get-FusionTerminals | Where-Object { $_.SessionId -eq $session })
    if ($local.Count -ne 1) {
        Add-Content -LiteralPath $log -Value "$stamp launch did not establish exactly one terminal in interactive session $session"
        exit 2
    }
}

# A HUNG DESK TERMINAL IS RESTARTED, NOT WAITED ON (2026-11-17). After the 11-16 reboot the one
# interactive Fusion terminal stopped answering every reader for ~22h while this watchdog logged
# "probe failed" each pass, and a restart waited on the principal. The principal's order is that
# nothing waits on him. Failed probes are counted in a small local file; the terminal is restarted
# only when ALL of these hold, and every restart is journalled to this log and the event log:
#   * >= $HungProbes consecutive failed probes spanning >= $HungMinutes minutes (not one blip);
#   * the book is safe to interrupt: the last published account state shows 0 open positions, or
#     data/GATEWAY_PAUSED is set -- OR the hang has lasted >= $HungUnmanagedMinutes minutes, when
#     a terminal that answers nothing is already managing nothing (positions and their stops live
#     on the broker's server; a restart closes none of them);
#   * no restart in the last $RestartCooldownMinutes minutes, and fewer than $MaxRestartsPerDay
#     restarts this UTC day (a terminal that hangs again on start is a fault for a person, not a
#     loop: the cap journals RESTART_CAP and holds);
#   * the failures are the probe's OWN "terminal did not answer" code (rc 2, initialize failed).
#     rc 99 (python or the probe missing) and rc 1 (an import error, a traceback, account_info
#     None) say the PROBE is broken, not the terminal; counting them would end a working desk
#     terminal every hour after a bad push (Auditor MF2, 2026-11-17).
$HungProbes = 3
$HangCode = 2
$MaxRestartsPerDay = 3
$HungMinutes = 15
$HungUnmanagedMinutes = 60
$RestartCooldownMinutes = 60
$hungPath = Join-Path $root 'desks\mt5\logs\terminal_probe_failures.json'
$events = Join-Path $root 'desks\mt5\data\events.jsonl'

function Write-Event([hashtable]$fields) {
    $row = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss+00:00');
                       producer = 'MT5-TerminalBoot'; host = $env:COMPUTERNAME }
    foreach ($k in $fields.Keys) { $row[$k] = $fields[$k] }
    $row['ack_state'] = 'UNACKNOWLEDGED'
    try {
        Add-Content -LiteralPath $events -Value ($row | ConvertTo-Json -Compress) -Encoding UTF8
    } catch {
        Add-Content -LiteralPath $log -Value "$stamp event log not written: $($_.Exception.GetType().Name)"
    }
}

function Read-Hung {
    try { return (Get-Content -LiteralPath $hungPath -Raw | ConvertFrom-Json) } catch { return $null }
}

# THE COOLDOWN OUTLIVES A PASSING PROBE. The file is never deleted: a pass resets the failure
# count but keeps last_restart_at, or a terminal that answers once and hangs again would be
# restarted every three probes forever (Auditor MF1, 2026-11-17).
function Write-HungCleared($kept) {
    $cleared = [ordered]@{ first_fail_at = $null; count = 0;
                           last_restart_at = $(if ($kept) { $kept.last_restart_at } else { $null });
                           restart_day = $(if ($kept) { $kept.restart_day } else { $null });
                           restarts_on_day = $(if ($kept -and $kept.restarts_on_day) { [int]$kept.restarts_on_day } else { 0 }) }
    try { $cleared | ConvertTo-Json -Compress | Set-Content -LiteralPath $hungPath -Encoding UTF8 } catch { }
}

$probeCode = Invoke-ReadOnlyProbe
if ($probeCode -ne 0 -and $probeCode -ne $HangCode) {
    # The probe itself is broken: never counted toward a restart, and the count is left as it was.
    Add-Content -LiteralPath $log -Value "$stamp probe rc=$probeCode is not the hang code; terminal restart count untouched"
    exit 2
}
if ($probeCode -eq $HangCode) {
    $now = (Get-Date).ToUniversalTime()
    $prev = Read-Hung
    $first = $now; $count = 1; $lastRestart = $null
    # not ISO: PS7 ConvertFrom-Json would read an ISO date back as a DateTime
    $today = $now.ToString('yyyyMMdd'); $restartsToday = 0
    if ($prev -and $prev.restart_day -eq $today -and $prev.restarts_on_day) { $restartsToday = [int]$prev.restarts_on_day }
    if ($prev) {
        try { $first = [datetime]::Parse($prev.first_fail_at).ToUniversalTime() } catch { $first = $now }
        $count = [int]$prev.count + 1
        if ($prev.last_restart_at) {
            try { $lastRestart = [datetime]::Parse($prev.last_restart_at).ToUniversalTime() } catch { $lastRestart = $null }
        }
    }
    $hungMin = ($now - $first).TotalMinutes
    $state = [ordered]@{ first_fail_at = $first.ToString('o'); count = $count;
                         last_restart_at = $(if ($lastRestart) { $lastRestart.ToString('o') } else { $null });
                         restart_day = $today; restarts_on_day = $restartsToday }
    $positions = $null
    try {
        $acct = Get-Content -LiteralPath (Join-Path $root 'desks\mt5\data\account_state.json') -Raw | ConvertFrom-Json
        if ($null -ne $acct.open_positions) { $positions = [int]$acct.open_positions }
    } catch { $positions = $null }
    $paused = Test-Path -LiteralPath (Join-Path $root 'desks\mt5\data\GATEWAY_PAUSED')
    $safe = ($positions -eq 0) -or $paused -or ($hungMin -ge $HungUnmanagedMinutes)
    $cooled = (-not $lastRestart) -or (($now - $lastRestart).TotalMinutes -ge $RestartCooldownMinutes)
    $underCap = $restartsToday -lt $MaxRestartsPerDay
    if ($count -ge $HungProbes -and $hungMin -ge $HungMinutes -and $safe -and $cooled -and $underCap -and $local.Count -eq 1) {
        $old = $local[0].Id
        $stopped = $true
        try { Stop-Process -Id $old -Force -ErrorAction Stop } catch { $stopped = $false }
        Start-Sleep -Seconds 5
        if ($stopped) { Start-Process -FilePath $exe -WindowStyle Hidden; Start-Sleep -Seconds 30 }
        $after = Invoke-ReadOnlyProbe
        $verdict = if (-not $stopped) { 'stop FAILED' } elseif ($after -eq 0) { 'restarted, probe passed' } else { 'restarted, probe still failing' }
        Add-Content -LiteralPath $log -Value ("$stamp JOURNAL hung Fusion terminal pid $old ($count failed probes over " +
            "$([math]::Round($hungMin)) min; open_positions=$positions paused=$paused) $verdict")
        Write-Event @{ kind = 'TERMINAL_HUNG_RESTARTED'; pid = $old; failed_probes = $count;
                       hung_minutes = [math]::Round($hungMin); open_positions = $positions;
                       paused = $paused; outcome = $verdict }
        $state.last_restart_at = $now.ToString('o')
        $state.restarts_on_day = $restartsToday + 1
        if ($after -eq 0) {
            Write-HungCleared ([pscustomobject]$state)
            $local = @(Get-FusionTerminals | Where-Object { $_.SessionId -eq $session })
            $newPid = if ($local.Count -ge 1) { $local[0].Id } else { 0 }
            Write-BootHealth $newPid " (after a hung-terminal restart)"
            exit 0
        }
        $state.first_fail_at = $now.ToString('o'); $state.count = 0
    } elseif ($count -ge $HungProbes -and -not $underCap) {
        Add-Content -LiteralPath $log -Value ("$stamp JOURNAL RESTART_CAP: $restartsToday terminal restarts today; " +
            "holding until the UTC day turns (a terminal that keeps hanging is a fault for a person)")
        if ($count -eq $HungProbes) {             # once per held episode, not every pass
            Write-Event @{ kind = 'TERMINAL_HUNG_RESTARTED'; outcome = 'RESTART_CAP held'; failed_probes = $count;
                           restarts_today = $restartsToday }
        }
    } elseif ($count -ge $HungProbes) {
        Add-Content -LiteralPath $log -Value ("$stamp terminal unanswering for $count probes over $([math]::Round($hungMin)) min; " +
            "restart held (open_positions=$positions paused=$paused cooled=$cooled local=$($local.Count))")
    }
    try { $state | ConvertTo-Json -Compress | Set-Content -LiteralPath $hungPath -Encoding UTF8 } catch { }
    exit 2
}
Write-HungCleared (Read-Hung)
Write-BootHealth $local[0].Id ""
exit 0
