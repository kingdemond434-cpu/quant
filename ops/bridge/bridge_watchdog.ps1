<#
.SYNOPSIS
    Keep the box bridge (`claude remote-control` in C:\opt\bridge\quant) running: start it, wait
    on it, and start it again whenever it exits.

.DESCRIPTION
    THE FAILURE THIS EXISTS FOR (2026-10-28). The bridge was started by hand inside zuck's RDP
    session and went offline minutes later. Server mode exits on its own after about ten minutes
    without the network, on a sign-in or policy error, or when anything stops the process, and
    nothing brought it back. The only fix was zuck opening RDP and typing the command again, so
    every box step routed through the bridge waited on him.

    WHAT IT DOES
        one instance per user (a named mutex), so the 5-minute re-arm never starts a second copy
        adopts a server that is already running (started by hand) and waits on it, rather than
        starting a second server in the same directory
        starts `claude remote-control --spawn worktree --no-create-session-in-dir --name
        <host>-bridge` in the checkout,
        in its own console, with a --debug-file per day under C:\opt\bridge\logs
        waits for it to exit, records why (exit code, how long it ran), and starts it again:
            ran >= 5 min        -> restart after 10 s (a network drop or a normal stop)
            ran <  5 min        -> back off 30 s, 60 s, ... up to 15 min (a crash loop)
            sign-in / trust     -> 30 min, and the heartbeat says needs_login, because
            / policy failure       restarting cannot fix a missing sign-in
        writes C:\opt\bridge\logs\bridge_watchdog.json on every transition (the liveness record
        Desk health and the hourly pass read)

    WHAT IT DOES NOT DO
        It adds no flag that changes what the sessions may do (no --permission-mode): the
        sessions keep the permissions the user's own settings give them. It never signs in, never
        stores a credential, and never touches C:\opt\quant.

.PARAMETER Checkout
    The bridge checkout. Default C:\opt\bridge\quant.
#>
[CmdletBinding()]
param(
    [string] $Checkout = "C:\opt\bridge\quant",
    [string] $LogDir = "C:\opt\bridge\logs",
    [string] $Name = ("{0}-bridge" -f $env:COMPUTERNAME.ToLower())
)

$ErrorActionPreference = "Continue"
$null = New-Item -ItemType Directory -Force -Path $LogDir -ErrorAction SilentlyContinue
$script:Log = Join-Path $LogDir "bridge_watchdog.log"
$script:Beat = Join-Path $LogDir "bridge_watchdog.json"
$script:State = @{ started_at = (Get-Date).ToUniversalTime().ToString("o"); restarts = 0
                   watchdog_pid = $PID; user = $env:USERNAME; checkout = $Checkout }

function Log([string] $m) {
    $line = "$((Get-Date).ToUniversalTime().ToString('u')) bridge-watchdog: $m"
    try { Add-Content -Path $script:Log -Value $line -Encoding utf8 -ErrorAction Stop } catch { }
}
function Beat([hashtable] $f) {
    foreach ($k in $f.Keys) { $script:State[$k] = $f[$k] }
    $script:State["at"] = (Get-Date).ToUniversalTime().ToString("o")
    try { ($script:State | ConvertTo-Json -Depth 3) | Set-Content -Path $script:Beat -Encoding utf8 -ErrorAction Stop } catch { }
}

# ONE WATCHDOG PER USER. The task re-arms every five minutes so a killed watchdog comes back; the
# mutex makes every re-arm while this one lives a no-op.
$mutex = New-Object System.Threading.Mutex($false, "Local\Claude-Bridge-Watchdog")
$owned = $false
try { $owned = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
if (-not $owned) { exit 0 }

$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    foreach ($c in @("$env:USERPROFILE\.local\bin\claude.exe", "$env:LOCALAPPDATA\Programs\claude\claude.exe")) {
        if (Test-Path $c) { $claude = $c; break }
    }
}
if (-not $claude) { Log "claude not found on PATH or in the default install paths"; Beat @{ state = "NO_CLAUDE" }; exit 2 }
if (-not (Test-Path (Join-Path $Checkout ".git"))) { Log "no checkout at $Checkout"; Beat @{ state = "NO_CHECKOUT" }; exit 2 }

function Get-RunningServer {
    @(Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -match '\sremote-control(\s|$)' })
}

# The messages that restarting cannot cure: the server exits at once on each, and a tight loop of
# them only fills the log. Matched against the tail of the day's debug file.
$NeedsHuman = 'requires a claude\.ai subscription|not logged in|/login|Workspace not trusted|disabled by your organization|Enable Remote Control\?'

$backoff = 30
Log "watchdog up (pid $PID, claude $claude, checkout $Checkout)"
Beat @{ state = "STARTING" }
while ($true) {
    $existing = Get-RunningServer
    if ($existing.Count -gt 0) {
        $p = $existing[0]
        Log "adopting running server pid $($p.ProcessId); waiting on it"
        Beat @{ state = "RUNNING"; server_pid = $p.ProcessId; server_started_by = "other" }
        try { Wait-Process -Id $p.ProcessId -ErrorAction SilentlyContinue } catch { }
        Log "server pid $($p.ProcessId) exited"
        Start-Sleep -Seconds 10
        continue
    }

    $day = (Get-Date).ToUniversalTime().ToString("yyyyMMdd")
    $debug = Join-Path $LogDir "rc_debug_$day.log"
    # --no-create-session-in-dir: thread sessions are spawned on demand, so a pre-created session per
    # restart would only pile up idle sessions in the list after every network drop.
    $rcArgs = @("remote-control", "--spawn", "worktree", "--no-create-session-in-dir", "--name", $Name,
                "--debug-file", $debug)
    $t0 = Get-Date
    try {
        $proc = Start-Process -FilePath $claude -ArgumentList $rcArgs -WorkingDirectory $Checkout `
            -WindowStyle Minimized -PassThru -ErrorAction Stop
    } catch {
        Log "start failed: $($_.Exception.Message)"
        Beat @{ state = "START_FAILED"; last_error = $_.Exception.Message }
        Start-Sleep -Seconds $backoff
        $backoff = [Math]::Min($backoff * 2, 900)
        continue
    }
    $script:State.restarts = [int]$script:State.restarts + 1
    Log "started server pid $($proc.Id) (start #$($script:State.restarts))"
    Beat @{ state = "RUNNING"; server_pid = $proc.Id; server_started_by = "watchdog"
            server_started_at = $t0.ToUniversalTime().ToString("o") }
    $proc.WaitForExit()
    $ran = [int]((Get-Date) - $t0).TotalSeconds
    $code = $null
    try { $code = $proc.ExitCode } catch { }

    $tail = ""
    try { $tail = (Get-Content -Path $debug -Tail 60 -ErrorAction Stop) -join "`n" } catch { }
    if ($ran -lt 300 -and $tail -match $NeedsHuman) {
        $why = $Matches[0]
        Log "server exited after ${ran}s with exit $code and '$why': needs a person; retrying in 30 min"
        Beat @{ state = "NEEDS_LOGIN"; last_exit_code = $code; last_ran_s = $ran; needs = $why }
        Start-Sleep -Seconds 1800
        continue
    }
    if ($ran -ge 300) { $backoff = 10 }
    Log "server exited after ${ran}s with exit $code; restarting in ${backoff}s"
    Beat @{ state = "RESTARTING"; last_exit_code = $code; last_ran_s = $ran; next_in_s = $backoff }
    Start-Sleep -Seconds $backoff
    $backoff = if ($ran -ge 300) { 30 } else { [Math]::Min([Math]::Max($backoff, 30) * 2, 900) }
}
