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
        starts `claude remote-control --spawn <SpawnMode> --no-create-session-in-dir --name <Name>`
        in the checkout, in its own console, with a --debug-file of its own per run. SpawnMode is
        same-dir by default (zuck's choice, 2026-10-28 06:13Z), and then with --capacity 1: rule
        R0423 forbids two live sessions sharing one worktree, and the CLI's default is 32.
        worktree stays selectable (no capacity flag) once a trial on the box shows it works
        asks git every 5 min whether it accepts the checkout; when git calls it "dubious ownership"
        (it did on 2026-10-28: owned by BUILTIN\Administrators, so every worktree session parked)
        the heartbeat carries git_refusal and the reader says GIT_REFUSED
        refreshes C:\ProgramData\ClaudeBridge\logs\bridge_watchdog.json at least every 60 s -- while the server
        runs AND through every back-off or sign-in wait (`at`, `beat_every_s`, server pid, how long
        the server's debug file has been silent, session errors the debug file names), so a reader
        can tell a live watchdog from a hung one and a connected server from one parked at a prompt
        refuses to run unless the bin and log folders (under C:\ProgramData\ClaudeBridge) are
        Administrators + SYSTEM only (the log folder readable by Users), nothing in them or on the
        way to them is a junction or symlink, and no folder on the way can be renamed, re-owned or
        re-permissioned by anyone else: the watchdog runs elevated, so a folder anyone can write --
        or a parent anyone can rename and replace -- is a planted script run elevated, a forged
        heartbeat and, through a junction, an elevated write or delete anywhere
        reports (never refuses over) a bridge checkout that a non-admin could write or replace: the
        sessions run elevated in it and load its hooks, so the reader flags it until it is locked
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
        the desk's live checkout. ops\bridge\bridge_status.ps1 is the read-only reader of its heartbeat.
#>
[CmdletBinding()]
param(
    [string] $Checkout = "C:\opt\bridge\quant",
    [string] $LogDir = "C:\ProgramData\ClaudeBridge\logs",
    [string] $Name = ("{0}-bridge" -f $env:COMPUTERNAME.ToLower()),
    [ValidateSet("same-dir", "worktree")] [string] $SpawnMode = "same-dir"
)

$ErrorActionPreference = "Continue"
$BinDir = Split-Path -Parent $PSCommandPath

# ONLY ADMINISTRATORS AND SYSTEM MAY WRITE WHERE THIS ELEVATED SCRIPT WRITES, OR REPLACE IT (audit
# v1.1 MF2, v1.2 MF1). The installer creates and locks both folders under C:\ProgramData, whose own
# ACL lets nobody but administrators rename or re-permission what an administrator created there;
# this script never creates them, and refuses -- before it writes a byte -- when either grants
# write to anyone else or is owned by anyone else, when any file inside or any folder on the way
# is a reparse point (junction, symlink, mount point), or when anyone else may delete, rename,
# re-own or re-permission any folder on the way (a renamed parent is a replaced bin).
$AdminSids = @("S-1-5-32-544", "S-1-5-18", "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464")
# Write rights on a folder this script writes to; and on a folder above it, the rights that let
# someone delete, rename, re-own or re-permission it (creating a sibling is harmless).
$WriteMask = [int64]([System.Security.AccessControl.FileSystemRights]"Write, Delete, DeleteSubdirectoriesAndFiles, ChangePermissions, TakeOwnership") -bor 0x50000000
$ParentMask = [int64]([System.Security.AccessControl.FileSystemRights]"Delete, DeleteSubdirectoriesAndFiles, ChangePermissions, TakeOwnership") -bor 0x10000000
function Get-AclProblem([string] $path, [int64] $mask, [string[]] $owners = $AdminSids) {
    $acl = Get-Acl -LiteralPath $path -ErrorAction Stop
    $owner = (New-Object System.Security.Principal.NTAccount($acl.Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($owner -notin $owners) { return "$path is owned by $($acl.Owner)" }
    foreach ($a in $acl.Access) {
        if ($a.AccessControlType -ne "Allow") { continue }
        if ($a.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]::InheritOnly) { continue }
        $sid = try { $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { [string]$a.IdentityReference }
        if ($sid -in $AdminSids) { continue }
        if (([int64]$a.FileSystemRights -band $mask) -ne 0) { return "$path grants $($a.FileSystemRights) to $($a.IdentityReference)" }
    }
    return $null
}
function Get-UnsafeReason([string] $dir, [switch] $Shallow, [string[]] $owners = $AdminSids) {
    try {
        $item = Get-Item -LiteralPath $dir -Force -ErrorAction Stop
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { return "$($item.FullName) is a reparse point" }
        $walk = $item.Parent
        while ($walk) {
            if ($walk.Attributes -band [IO.FileAttributes]::ReparsePoint) { return "$($walk.FullName) is a reparse point" }
            $why = Get-AclProblem $walk.FullName $ParentMask
            if ($why) { return $why }
            $walk = $walk.Parent
        }
        if (-not $Shallow) {
            foreach ($c in @(Get-ChildItem -LiteralPath $dir -Force -ErrorAction Stop)) {
                if ($c.Attributes -band [IO.FileAttributes]::ReparsePoint) { return "$($c.FullName) is a reparse point" }
            }
        }
        return (Get-AclProblem $dir $WriteMask $owners)
    } catch { return "$dir cannot be examined: $($_.Exception.Message)" }
}
function Assert-SafeFolders {
    foreach ($d in @($BinDir, $LogDir)) {
        $why = Get-UnsafeReason $d
        # Nothing is written anywhere: the folder that would carry the message is the unsafe one.
        # The task's last result (4) and bridge_status.ps1's own folder check say why.
        if ($why) { exit 4 }
    }
}
Assert-SafeFolders
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
# `beat_every_s` is the promise a reader holds the heartbeat to: 60 while this process lives; a
# state written just before exit (TAMPERED, NO_CLAUDE, ...) promises the task's 5-minute re-arm.
function Beat([hashtable] $f) {
    $script:State["beat_every_s"] = 60
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
    Beat @{ state = "TAMPERED"; pinned_sha256 = $pinned; beat_every_s = 300 }
    exit 3
}

# KNOWN INSTALL PATHS FIRST, PATH LAST (audit v1.5): the first claude or git on an elevated PATH
# wins, so a writable folder early on PATH would be code run elevated. Where each one lives is
# measured every pass (binary_risk) like the checkout.
$claude = $null
foreach ($cand in @("$env:USERPROFILE\.local\bin\claude.exe", "$env:LOCALAPPDATA\Programs\claude\claude.exe")) {
    if (Test-Path -LiteralPath $cand) { $claude = $cand; break }
}
if (-not $claude) { $claude = (Get-Command claude -ErrorAction SilentlyContinue).Source }
if (-not $claude) { Log "claude not found on PATH or in the default install paths"; Beat @{ state = "NO_CLAUDE"; beat_every_s = 300 }; exit 2 }
if (-not (Test-Path (Join-Path $Checkout ".git"))) { Log "no checkout at $Checkout"; Beat @{ state = "NO_CHECKOUT"; beat_every_s = 300 }; exit 2 }

# THE CHECKOUT THE ELEVATED SESSIONS RUN IN. Whoever can write it, its .claude or its git hooks, or
# rename a folder above it, runs code in those sessions. Not a reason to leave the bridge down --
# it is how the bridge ran by hand -- so it is measured every pass and carried in the heartbeat.
$script:MySid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
function Get-CheckoutRisk {
    foreach ($d in @($Checkout, (Join-Path $Checkout ".claude"), (Join-Path $Checkout ".git"),
                     (Join-Path $Checkout ".git\hooks"))) {
        if (-not (Test-Path -LiteralPath $d)) { continue }
        # the checkout stays owned by this (administrator) user: git refuses one owned by another
        $why = Get-UnsafeReason $d -Shallow -owners ($AdminSids + $script:MySid)
        if ($why) { return $why }
    }
    return $null
}

# GIT MUST ACCEPT THE CHECKOUT (2026-10-28, Desk health). With the checkout owned by
# BUILTIN\Administrators and the bridge running as its own user, git refused the repository as
# "dubious ownership" and every session parked with "Failed to create worktree ... git metadata that
# could not be resolved", while the server stayed up. The installer makes this user the owner; this
# asks git itself, in a job with a timeout, at most every 5 minutes. Reported, never fatal.
$script:Git = $null
foreach ($cand in @("$env:ProgramFiles\Git\cmd\git.exe", "$env:ProgramFiles\Git\bin\git.exe")) {
    if (Test-Path -LiteralPath $cand) { $script:Git = $cand; break }
}
if (-not $script:Git) { $script:Git = (Get-Command git -ErrorAction SilentlyContinue).Source }
# Where the two programs this elevated script runs live: no one but administrators, SYSTEM and
# this user may write the folder or rename, re-own or re-permission a folder above it.
function Get-BinaryRisk {
    foreach ($exe in @($claude, $script:Git)) {
        if (-not $exe) { continue }
        try {
            $item = Get-Item -LiteralPath (Split-Path -Parent $exe) -Force -ErrorAction Stop
            $why = Get-AclProblem $item.FullName $WriteMask ($AdminSids + $script:MySid)
            $walk = $item
            while (-not $why -and $walk) {
                if ($walk.Attributes -band [IO.FileAttributes]::ReparsePoint) { $why = "$($walk.FullName) is a reparse point" }
                elseif ($walk -ne $item) { $why = Get-AclProblem $walk.FullName $ParentMask ($AdminSids + $script:MySid) }
                $walk = $walk.Parent
            }
            if ($why) { return "$($exe): $why" }
        } catch { return "$exe cannot be examined: $($_.Exception.Message)" }
    }
    return $null
}
$script:GitChecked = [datetime]::MinValue
$script:GitRefusal = $null
function Get-GitRefusal {
    if (-not $script:Git) { return "git not found on PATH" }
    if (((Get-Date) - $script:GitChecked).TotalSeconds -lt 300) { return $script:GitRefusal }
    $script:GitChecked = Get-Date
    $job = Start-Job -ArgumentList $script:Git, $Checkout -ScriptBlock { param($g, $d) & $g -C $d rev-parse --git-dir 2>&1 | Out-String }
    $out = $null
    if (Wait-Job -Job $job -Timeout 60) { $out = (Receive-Job -Job $job -ErrorAction SilentlyContinue | Out-String) }
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    $script:GitRefusal = $null
    if ($null -eq $out) { $script:GitRefusal = "git rev-parse did not answer within 60 s" }
    elseif ($out -match '(?i)dubious ownership|not a git repository|unsafe repository') {
        $script:GitRefusal = $out.Trim().Substring(0, [Math]::Min(300, $out.Trim().Length))
    }
    return $script:GitRefusal
}

# SLEEP, BUT KEEP SAYING SO (audit v1.1 MF1). A 30-minute sign-in wait or a 15-minute back-off with
# no heartbeat read as "watchdog hung" for most of the wait. Sleep in chunks of at most 60 s and
# beat each one, carrying when the wait ends.
function Wait-Beating([int] $seconds, [hashtable] $f) {
    $until = (Get-Date).AddSeconds([Math]::Max($seconds, 1))
    $f["next_at"] = $until.ToUniversalTime().ToString("o")
    while ($true) {
        Assert-SafeFolders
        $left = [int][Math]::Ceiling(($until - (Get-Date)).TotalSeconds)
        $f["next_in_s"] = [Math]::Max($left, 0)
        Beat $f
        if ($left -le 0) { break }
        Start-Sleep -Seconds ([Math]::Min(60, $left))
    }
}

# A DEBUG FILE IS READ ONLY WHEN IT IS THIS WATCHDOG'S: a plain file directly in the locked log folder.
function Get-OwnDebug([string] $path) {
    if (-not $path) { return $null }
    try {
        $full = [IO.Path]::GetFullPath($path)
        if ((Split-Path -Parent $full) -ne [IO.Path]::GetFullPath($LogDir)) { return $null }
        if ((Split-Path -Leaf $full) -notmatch '^rc_debug_\d{8}_\d{6}\.log$') { return $null }
        return $full
    } catch { return $null }
}

# THE SERVER THIS WATCHDOG STARTED: pid + start time, so a recycled pid is never mistaken for it,
# and its debug file, so a server found again after a watchdog restart is still measured. The
# start time is compared as ticks: Windows PowerShell reads it back as a string and PowerShell 7
# as a DateTime, and both carry 100 ns.
function Get-TrackedServer {
    try {
        $rec = Get-Content -Path $script:PidFile -Raw -ErrorAction Stop | ConvertFrom-Json
        $p = Get-Process -Id ([int]$rec.pid) -ErrorAction Stop
        $want = ([datetime]$rec.start).ToUniversalTime().Ticks
        if ($p.StartTime.ToUniversalTime().Ticks -eq $want) {
            return @{ Proc = $p; Debug = (Get-OwnDebug ([string]$rec.debug)) }
        }
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
            ForEach-Object {
                $d = ""
                if ($_.CommandLine -match '--debug-file\s+"?([^"\s]+)') { $d = $Matches[1] }
                # same-dir (any spawn but worktree) without --capacity 1 breaks R0423
                $open = ($_.CommandLine -notmatch '--spawn\s+"?worktree') -and ($_.CommandLine -notmatch '--capacity\s+"?1"?(\s|$)')
                "{0}|{1}|{2}" -f $_.ProcessId, $d, $open
            }
    }
    $rows = @()
    if (Wait-Job -Job $job -Timeout 20) { $rows = @(Receive-Job -Job $job -ErrorAction SilentlyContinue) }
    else { Log "process query timed out after 20 s; not adopting this pass" }
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    foreach ($row in $rows) {
        $id, $d, $open = "$row".Split("|", 3)
        $p = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
        if ($p) { return @{ Proc = $p; Debug = (Get-OwnDebug $d); Uncapped = ($open -eq "True") } }
    }
    return $null
}

# SESSIONS THAT DIE, NOT ONLY A SERVER THAT DIES (2026-10-28, the E8 thread: three sessions on this
# bridge parked within a second of starting while the server process stayed up). A process-alive
# check cannot see that, so each beat reads only the lines the server's debug file gained since the
# last beat and counts those naming a failed or exited session or spawn; the heartbeat carries the
# count over the last 10 minutes and the newest line. History already in a file when it is first
# seen is not counted. A reader reports it; the watchdog never restarts a server over it. Both
# patterns are first guesses, to calibrate on the box ($SessionNoise: lines seen on a healthy server).
# The 2026-10-28 parks read "Failed to create worktree ...": the failure word comes first.
# Narrowed after audit v1.5: "MCP server ... failed to start" and a DNS name that "could not be
# resolved" are not parked sessions.
$SessionError = '(?i)(session|spawn|worktree|child).{0,80}(fail|error|exited|crash|refus|denied)|fail\w*\s+to\s+(create|spawn|start)\s+(a\s+)?(worktree|session|child)|dubious ownership|git metadata that could not be resolved'
$SessionNoise = '(?i)updateSessionTitle'
$script:DebugPos = @{}
$script:ErrTimes = @()
$script:LastErr = $null
function Update-SessionErrors([string] $debug, [bool] $ours) {
    if (-not $debug -or -not (Test-Path -LiteralPath $debug)) { return @{ n = $null; last = $null } }
    $now = Get-Date
    try {
        $fs = [IO.File]::Open($debug, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]"ReadWrite, Delete")
        try {
            $len = $fs.Length
            # A file this watchdog created is read from its first byte: sessions park within a
            # second of the start, before the first beat. Only history found in a server adopted
            # from earlier is skipped.
            if (-not $script:DebugPos.ContainsKey($debug)) { $script:DebugPos[$debug] = $(if ($ours) { 0 } else { $len }) }
            $pos = [int64]$script:DebugPos[$debug]
            if ($pos -gt $len) { $pos = 0 }
            $pos = [Math]::Max($pos, $len - 4MB)
            $null = $fs.Seek($pos, [IO.SeekOrigin]::Begin)
            $new = (New-Object IO.StreamReader($fs)).ReadToEnd()
            $script:DebugPos[$debug] = $len
        } finally { $fs.Dispose() }
        foreach ($l in ($new -split "`n")) {
            if ($l -match $SessionError -and $l -notmatch $SessionNoise) {
                $script:ErrTimes += $now
                $script:LastErr = $l.Trim().Substring(0, [Math]::Min(300, $l.Trim().Length))
            }
        }
    } catch { return @{ n = $null; last = $script:LastErr } }
    $cut = $now.AddMinutes(-10)
    $script:ErrTimes = @($script:ErrTimes | Where-Object { $_ -ge $cut })
    return @{ n = $script:ErrTimes.Count; last = $script:LastErr }
}

function Wait-Server([System.Diagnostics.Process] $p, [string] $debug, [string] $by) {
    $null = $p.Handle   # without a handle taken before exit, ExitCode can read back null
    while (-not $p.WaitForExit(60000)) {
        Assert-SafeFolders
        # null = UNMEASURED (no debug file of ours to read), never "quiet for 0 s"
        $quiet = $null
        if ($debug -and (Test-Path -LiteralPath $debug)) {
            $quiet = [int]((Get-Date) - (Get-Item -LiteralPath $debug).LastWriteTime).TotalSeconds
        }
        $se = Update-SessionErrors $debug ($by -eq "watchdog")
        Beat @{ state = "RUNNING"; server_pid = $p.Id; server_started_by = $by; debug_file = $debug
                debug_quiet_s = $quiet; session_errors_10m = $se.n; last_session_error = $se.last
                checkout_risk = (Get-CheckoutRisk); git_refusal = (Get-GitRefusal); spawn_mode = $SpawnMode
                binary_risk = (Get-BinaryRisk); server_risk = $script:ServerRisk
                next_at = $null; next_in_s = $null; needs = $null }
    }
}

# NOT SIGNED IN ONLY WHEN `auth status` SAYS SO. Its default output is JSON with "loggedIn"; that
# field decides. A non-zero exit or unparseable output alone is unmeasured and counts as a crash
# (back-off), never as 30 minutes of NEEDS_LOGIN. A token signed in but refused by remote-control
# (the "full-scope login" refusal) reads loggedIn: true here; only the debug file can show it.
function Test-SignedIn {
    $job = Start-Job -ArgumentList $claude -ScriptBlock { param($c) $o = & $c auth status 2>&1 | Out-String; "$LASTEXITCODE|$o" }
    $out = $null
    if (Wait-Job -Job $job -Timeout 60) { $out = (Receive-Job -Job $job -ErrorAction SilentlyContinue | Out-String) }
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    if (-not $out) { return $true }
    $rc, $text = $out.Split("|", 2)
    try {
        $j = $text | ConvertFrom-Json -ErrorAction Stop
        if ($null -ne $j.loggedIn) { return [bool]$j.loggedIn }
    } catch { }
    return -not ($text -match '(?i)not (logged|signed) in')
}

function Remove-OldDebugFiles {
    Get-ChildItem -Path $LogDir -Filter "rc_debug_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

$Refused = 'Workspace not trusted|disabled by your organization|Couldn''t verify your organization|requires a claude\.ai subscription|full-scope login'
$backoff = 30
Log "watchdog up (pid $PID, claude $claude, checkout $Checkout, name $Name, spawn $SpawnMode, sha $($mySha.Substring(0,12)))"
Beat @{ state = "STARTING" }
while ($true) {
    Assert-SafeFolders
    $existing = Get-TrackedServer
    # A SERVER STARTED BY HAND runs with whatever flags it was given (audit v1.6): adopted, never
    # stopped, but one sharing its checkout among many sessions is reported until it is replaced.
    $script:ServerRisk = $null
    if (-not $existing) {
        $existing = Find-NamedServer
        if ($existing -and $existing.Uncapped) {
            $script:ServerRisk = "adopted server pid $($existing.Proc.Id) shares its checkout without --capacity 1 (R0423); stop it once and this watchdog starts a capped one"
        }
    }
    if ($existing) {
        Log "waiting on running server pid $($existing.Proc.Id) (debug $($existing.Debug))"
        Wait-Server $existing.Proc $existing.Debug "earlier"
        Log "server pid $($existing.Proc.Id) exited"
        Wait-Beating 10 @{ state = "RESTARTING"; last_ran_s = $null }
        continue
    }

    Remove-OldDebugFiles
    $debug = Join-Path $LogDir ("rc_debug_{0}.log" -f (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss"))
    # --no-create-session-in-dir: thread sessions are spawned on demand, so a pre-created session per
    # restart would only pile up idle sessions in the list after every network drop.
    $rcArgs = @("remote-control", "--spawn", $SpawnMode, "--no-create-session-in-dir", "--name", $Name,
                "--debug-file", $debug)
    if ($SpawnMode -eq "same-dir") { $rcArgs += @("--capacity", "1") }
    $t0 = Get-Date
    try {
        $proc = Start-Process -FilePath $claude -ArgumentList $rcArgs -WorkingDirectory $Checkout `
            -WindowStyle Minimized -PassThru -ErrorAction Stop
    } catch {
        Log "start failed: $($_.Exception.Message)"
        Wait-Beating $backoff @{ state = "START_FAILED"; last_error = $_.Exception.Message }
        $backoff = [Math]::Min([Math]::Max($backoff, 30) * 2, 900)
        continue
    }
    $null = $proc.Handle
    try {
        @{ pid = $proc.Id; start = $proc.StartTime.ToUniversalTime().ToString("o"); debug = $debug } | ConvertTo-Json |
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
            Wait-Beating 1800 @{ state = "NEEDS_LOGIN"; last_exit_code = $code; last_ran_s = $ran; needs = $why }
            continue
        }
    }
    if ($ran -ge 300) { $backoff = 10 }
    Log "server exited after ${ran}s with exit $code; restarting in ${backoff}s"
    Wait-Beating $backoff @{ state = "RESTARTING"; last_exit_code = $code; last_ran_s = $ran }
    $backoff = if ($ran -ge 300) { 30 } else { [Math]::Min([Math]::Max($backoff, 30) * 2, 900) }
}
