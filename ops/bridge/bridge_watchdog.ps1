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
        refuses to run if its own bytes are not the ones the installer pinned (bin\watchdog.sha256
        in the admin-only folder): an elevated script nobody re-checks is a privilege escalation
        tracks the server it started by PID + start time in the admin-only bin folder, and adopts
        a server started earlier only when it is this user's AND carries `--name <Name>` -- never
        any user's `remote-control` in any directory. The one process query that can hang on this
        box (CIM) runs in a job with a timeout, so a hung query costs one pass, never the bridge
        starts `claude remote-control --spawn worktree --no-create-session-in-dir --name <Name>`
        in the checkout, in its own console, with a --debug-file of its own per run
        refreshes C:\opt\bridge\logs\bridge_watchdog.json every 60 s while the server runs (`at`,
        server pid, how long the server's debug file has been silent), so a reader can tell a
        live watchdog from a hung one and a connected server from one parked at a prompt
        restarts it when it exits:
            ran >= 5 min                -> after 10 s (a network drop or a normal stop)
            ran <  5 min, signed in     -> back off 30 s, 60 s, ... up to 15 min (a crash loop)
            ran <  5 min, `claude auth status` says not signed in, or THIS run's debug file names
            a trust/policy refusal      -> 30 min and state NEEDS_LOGIN; a restart cannot fix it
        keeps 14 days of per-run debug files and rolls its own log at 10 MB

    WHAT IT DOES NOT DO
        It adds no flag that changes what the sessions may do: the sessions keep the permissions
        the user's own settings give them. It never signs in, stores no credential, writes no
        environment variable, registry value or settings file, stops no process and never touches
        C:\opt\quant. ops\bridge\bridge_status.ps1 is the read-only reader of its heartbeat.
#>
[CmdletBinding()]
param(
    [string] $Checkout = "C:\opt\bridge\quant",
    [string] $LogDir = "C:\opt\bridge\logs",
    [string] $Name = ("{0}-bridge" -f $env:COMPUTERNAME.ToLower())
)

$ErrorActionPreference = "Continue"
$BinDir = Split-Path -Parent $PSCommandPath
$null = New-Item -ItemType Directory -Force -Path $LogDir -ErrorAction SilentlyContinue
$script:Log = Join-Path $LogDir "bridge_watchdog.log"
$script:Beat = Join-Path $LogDir "bridge_watchdog.json"
$script:PidFile = Join-Path $BinDir "server.pid"
$mySha = ""
try { $mySha = (Get-FileHash -Path $PSCommandPath -Algorithm SHA256).Hash.ToLower() } catch { }
$script:State = @{ started_at = (Get-Date).ToUniversalTime().ToString("o"); restarts = 0
                   watchdog_pid = $PID; user = $env:USERNAME; checkout = $Checkout; name = $Name
                   watchdog_sha256 = $mySha }

function Log([string] $m) {
    $line = "$((Get-Date).ToUniversalTime().ToString('u')) bridge-watchdog: $m"
    try {
        if ((Test-Path $script:Log) -and (Get-Item $script:Log).Length -gt 10MB) {
            Move-Item -Path $script:Log -Destination ($script:Log + ".1") -Force -ErrorAction Stop
        }
        Add-Content -Path $script:Log -Value $line -Encoding utf8 -ErrorAction Stop
    } catch { }
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

# THE BYTES THE INSTALLER PINNED. The installer writes this script's sha256 into the same
# admin-only folder; a copy that no longer matches is not run.
$pinFile = Join-Path $BinDir "watchdog.sha256"
$pinned = ""
try { $pinned = (Get-Content -Path $pinFile -Raw -ErrorAction Stop).Trim().ToLower() } catch { }
if (-not $mySha -or $mySha -ne $pinned) {
    Log "own sha256 $mySha does not match the installer's pin '$pinned'; not running"
    Beat @{ state = "TAMPERED"; pinned_sha256 = $pinned }
    exit 3
}

$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) {
    foreach ($c in @("$env:USERPROFILE\.local\bin\claude.exe", "$env:LOCALAPPDATA\Programs\claude\claude.exe")) {
        if (Test-Path $c) { $claude = $c; break }
    }
}
if (-not $claude) { Log "claude not found on PATH or in the default install paths"; Beat @{ state = "NO_CLAUDE" }; exit 2 }
if (-not (Test-Path (Join-Path $Checkout ".git"))) { Log "no checkout at $Checkout"; Beat @{ state = "NO_CHECKOUT" }; exit 2 }

# THE SERVER THIS WATCHDOG STARTED: pid + start time, so a recycled pid is never mistaken for it.
function Get-TrackedServer {
    try {
        $rec = Get-Content -Path $script:PidFile -Raw -ErrorAction Stop | ConvertFrom-Json
        $p = Get-Process -Id ([int]$rec.pid) -ErrorAction Stop
        if ($p.StartTime.ToUniversalTime().ToString("o") -eq [string]$rec.start) { return $p }
    } catch { }
    return $null
}

# A SERVER STARTED EARLIER UNDER THIS NAME BY THIS USER (by hand, or before a watchdog restart).
# CIM is the only way to read a command line and its owner, and CIM has hung on this box, so it
# runs in a job that is abandoned after 20 s: a hung query costs this pass, never the bridge.
function Find-NamedServer {
    $job = Start-Job -ArgumentList $Name, $env:USERNAME -ScriptBlock {
        param($n, $u)
        Get-CimInstance Win32_Process -Filter "Name = 'claude.exe'" |
            Where-Object { $_.CommandLine -match '\sremote-control(\s|$)' -and
                           $_.CommandLine -match ('--name\s+"?' + [regex]::Escape($n) + '"?(\s|$)') } |
            Where-Object { (Invoke-CimMethod -InputObject $_ -MethodName GetOwner).User -eq $u } |
            ForEach-Object { $_.ProcessId }
    }
    $ids = @()
    if (Wait-Job -Job $job -Timeout 20) { $ids = @(Receive-Job -Job $job -ErrorAction SilentlyContinue) }
    else { Log "process query timed out after 20 s; not adopting this pass" }
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    foreach ($id in $ids) {
        $p = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
        if ($p) { return $p }
    }
    return $null
}

function Wait-Server([System.Diagnostics.Process] $p, [string] $debug, [string] $by) {
    $null = $p.Handle   # without a handle taken before exit, ExitCode can read back null
    while (-not $p.WaitForExit(60000)) {
        $quiet = $null
        if ($debug -and (Test-Path $debug)) {
            $quiet = [int]((Get-Date) - (Get-Item $debug).LastWriteTime).TotalSeconds
        }
        Beat @{ state = "RUNNING"; server_pid = $p.Id; server_started_by = $by; debug_quiet_s = $quiet }
    }
}

function Test-SignedIn {
    $job = Start-Job -ArgumentList $claude -ScriptBlock { param($c) $o = & $c auth status 2>&1 | Out-String; "$LASTEXITCODE|$o" }
    $out = $null
    if (Wait-Job -Job $job -Timeout 60) { $out = (Receive-Job -Job $job -ErrorAction SilentlyContinue | Out-String) }
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    if (-not $out) { return $true }   # unmeasured: treat as a crash, never as a sign-in to wait out
    $rc, $text = $out.Split("|", 2)
    return -not ($rc.Trim() -ne "0" -or $text -match '(?i)not (logged|signed) in|claude auth.login|/login')
}

function Remove-OldDebugFiles {
    Get-ChildItem -Path $LogDir -Filter "rc_debug_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

$Refused = 'Workspace not trusted|disabled by your organization|Couldn''t verify your organization|requires a claude\.ai subscription|full-scope login'
$backoff = 30
Log "watchdog up (pid $PID, claude $claude, checkout $Checkout, name $Name, sha $($mySha.Substring(0,12)))"
Beat @{ state = "STARTING" }
while ($true) {
    $existing = Get-TrackedServer
    if (-not $existing) { $existing = Find-NamedServer }
    if ($existing) {
        Log "waiting on running server pid $($existing.Id)"
        Wait-Server $existing $null "earlier"
        Log "server pid $($existing.Id) exited"
        Start-Sleep -Seconds 10
        continue
    }

    Remove-OldDebugFiles
    $debug = Join-Path $LogDir ("rc_debug_{0}.log" -f (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss"))
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
    $null = $proc.Handle
    try {
        @{ pid = $proc.Id; start = $proc.StartTime.ToUniversalTime().ToString("o") } | ConvertTo-Json |
            Set-Content -Path $script:PidFile -Encoding utf8 -ErrorAction Stop
    } catch { Log "could not write $($script:PidFile): $($_.Exception.Message)" }
    $script:State.restarts = [int]$script:State.restarts + 1
    Log "started server pid $($proc.Id) (start #$($script:State.restarts)); debug $debug"
    Beat @{ state = "RUNNING"; server_pid = $proc.Id; server_started_by = "watchdog"
            server_started_at = $t0.ToUniversalTime().ToString("o"); debug_file = $debug }
    Wait-Server $proc $debug "watchdog"
    $ran = [int]((Get-Date) - $t0).TotalSeconds
    $code = $proc.ExitCode

    if ($ran -lt 300) {
        $tail = ""
        try { $tail = (Get-Content -Path $debug -Tail 80 -ErrorAction Stop) -join "`n" } catch { }
        $why = $null
        if ($tail -match $Refused) { $why = $Matches[0] }
        elseif (-not (Test-SignedIn)) { $why = "claude auth status: not signed in" }
        if ($why) {
            Log "server exited after ${ran}s with exit $code ($why): needs a person; retrying in 30 min"
            Beat @{ state = "NEEDS_LOGIN"; last_exit_code = $code; last_ran_s = $ran; needs = $why }
            Start-Sleep -Seconds 1800
            continue
        }
    }
    if ($ran -ge 300) { $backoff = 10 }
    Log "server exited after ${ran}s with exit $code; restarting in ${backoff}s"
    Beat @{ state = "RESTARTING"; last_exit_code = $code; last_ran_s = $ran; next_in_s = $backoff }
    Start-Sleep -Seconds $backoff
    $backoff = if ($ran -ge 300) { 30 } else { [Math]::Min([Math]::Max($backoff, 30) * 2, 900) }
}
