<#
.SYNOPSIS
    BOOT r25b BOX GUARDIAN, PHASE 1: READ-ONLY STATUS.

    Run by the r18c mover (QuantForge-BootMove, SYSTEM, every 5 min) through its guardian hook:
    the mover copies this file's committed blob at the current boot into an admin-only folder,
    re-hashes it against a fresh `git show`, and starts it with a 10 minute cap. Its failure never
    stops a boot move.

    WHY IT EXISTS. Since the r24 guard install (2026-11-27 17:20Z) the pinned MT5-AdoptRelease
    exits 2 and QuantGuard-RunAs exits 1 within seconds, both before writing any log. Their
    folders (guard\adopt, guard\runas) are SYSTEM/Administrators only, so no non-elevated reader
    can see why. This script, as SYSTEM, re-runs their early checks WITHOUT acting and writes
    what it found to one log the Users group can read.

    POWERS (Audit 2026-11-27 21:27Z; enforced by tests/ops/test_box_git_r25_guardian.py):
      * It WRITES two files only: C:\ProgramData\QuantBox\logs\guard_status.log (append) and,
        from phase 3, task_health.json beside it, through Write-Status, which refuses any other path. Nothing else, ever: not trust\,
        TRUST_SET, protect or the hooks, not an ACL, a task or its principal, not guard\adopt\venv
        or python.txt, not owner_approvals, verdicts or announced files, not RUN_AS.json, and
        nothing under C:\opt\quant.
      * It READS guard\adopt, guard\runas, the two tasks' definitions and their last results.
      * It RUNS only the guard's own pinned python with -c (the same isolation probe the pinned
        adopter runs, which prints sys.flags and sys.path and touches nothing) and dot-sources the
        guard checkout's git_acl.ps1 (a pure ACL reader).
      * It logs names, paths, exit codes and sys.path entries, never an environment value, a
        token or a key.
    Phase 2 (refreshing guard\adopt\tree to an Audit-cleared boot) is NOT in this file; Audit
    reviews it only after reading this phase's lines.

    PHASE 3 (output-based health, below) adds exactly two powers: it rewrites
    C:\ProgramData\QuantBox\logs\task_health.json (same file checks as the log), and it may
    Start-ScheduledTask a task NAMED in task_outputs.json at the current boot that is NOT running,
    within the bounds listed at that section. It never stops a task (Audit r25c MF1). It reads
    boot-src with `git show` only, and process command lines through CIM with a timeout.
#>
$ErrorActionPreference = 'Continue'
$Q      = 'C:\ProgramData\QuantBox'
$Guard  = Join-Path $Q 'guard'
$Adopt  = Join-Path $Guard 'adopt'
$Runas  = Join-Path $Guard 'runas'
$Live   = 'C:\opt\quant'
$LogDir = Join-Path $Q 'logs'
$Status = Join-Path $LogDir 'guard_status.log'
$Health = Join-Path $LogDir 'task_health.json'
$Forge  = Join-Path $Q 'forge'

function Test-PlainFile([string] $p) {
    # SYSTEM must never write through a link a non-admin planted: no reparse point on the folder
    # or the file, and exactly one hard link to the file.
    if ((Get-Item -LiteralPath $LogDir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
    if (-not (Test-Path -LiteralPath $p)) { return $true }
    if ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
    $links = @(& "$env:SystemRoot\System32\fsutil.exe" hardlink list $p 2>$null)
    if ($LASTEXITCODE -or $links.Count -ne 1) { return $false }
    return (Test-AdminFile $p)
}
function Test-AdminFile([string] $p) {
    # (Audit 21:40Z) a file a non-admin pre-created or can write is not ours: its lines (and the
    # hourly throttle read from them) could be spoofed. Owner Administrators or SYSTEM, and no
    # allow ACE granting any write to anyone else.
    try {
        $acl = Get-Acl -LiteralPath $p
        $own = (New-Object Security.Principal.NTAccount($acl.Owner)).Translate([Security.Principal.SecurityIdentifier]).Value
        if (@('S-1-5-32-544', 'S-1-5-18') -notcontains $own) { return $false }
        $w = [int]([Security.AccessControl.FileSystemRights]::WriteData -bor [Security.AccessControl.FileSystemRights]::AppendData -bor
                    [Security.AccessControl.FileSystemRights]::Delete -bor [Security.AccessControl.FileSystemRights]::ChangePermissions -bor
                    [Security.AccessControl.FileSystemRights]::TakeOwnership) -bor 0x50000000
        foreach ($r in $acl.Access) {
            if ("$($r.AccessControlType)" -ne 'Allow') { continue }
            $sid = $r.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
            if (@('S-1-5-32-544', 'S-1-5-18') -contains $sid) { continue }
            if ([int]$r.FileSystemRights -band $w) { return $false }
        }
        return $true
    } catch { return $false }
}
function New-AdminFile([string] $path) {
    # created once, with its own ACL and no inheritance: SYSTEM and Administrators full, Users
    # read. The only ACL this script ever sets, and only on its own two new files.
    $fs = New-Object Security.AccessControl.FileSecurity
    $fs.SetAccessRuleProtection($true, $false)
    foreach ($r in @(@('S-1-5-18', 'FullControl'), @('S-1-5-32-544', 'FullControl'), @('S-1-5-32-545', 'Read'))) {
        $fs.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
            (New-Object Security.Principal.SecurityIdentifier($r[0])), $r[1], 'Allow')))
    }
    $fs.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
    $h = [IO.File]::Create($path, 4096, [IO.FileOptions]::None, $fs); $h.Dispose()
}
function Write-Status([string] $path, [string] $line) {
    # THE ONLY WRITES IN THIS FILE: an append to guard_status.log, or a whole rewrite of
    # task_health.json. Any other target is refused, so a later edit cannot widen it without
    # changing this guard (and the test that pins it).
    if (@($Status, $Health) -notcontains $path) { throw "box_guardian: refused to write $path (only $Status, $Health)" }
    if (-not (Test-Path -LiteralPath $LogDir -PathType Container)) { return }
    if (-not (Test-PlainFile $path)) { return }
    if (-not (Test-Path -LiteralPath $path)) { New-AdminFile $path }
    $u8 = New-Object Text.UTF8Encoding($false)
    if ($path -eq $Status) {
        $row = '{0}  {1}' -f (Get-Date).ToUniversalTime().ToString('s'), $line
        [IO.File]::AppendAllText($Status, $row + "`r`n", $u8)
    } else {
        [IO.File]::WriteAllText($Health, $line, $u8)
    }
}
function Say([string] $m) { Write-Status $Status $m }
function Cut([string] $s, [int] $n = 400) {
    $s = "$s" -replace '\s+', ' '
    if ($s.Length -gt $n) { return $s.Substring(0, $n) + '...' }
    return $s
}

# The status block runs once an hour (the mover runs this every 5 minutes); task health runs
# every pass. The hour is read from
# the log itself (its last 'guardian status' line), so no second file is ever written.
$doStatus = $true
try {
    if ((Test-Path -LiteralPath $Status) -and (Test-AdminFile $Status)) {
        $last = Get-Content -LiteralPath $Status -Tail 400 | Where-Object { $_ -match '^\S+  guardian status begin' } | Select-Object -Last 1
        if ($last) {
            $at = [datetime]::Parse(($last -split '  ')[0], [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
            if (((Get-Date).ToUniversalTime() - $at).TotalMinutes -lt 55) { $doStatus = $false }
        }
    }
} catch { }

function Invoke-Status {
    Say 'guardian status begin (phase 1, read-only)'

    # 1. the two tasks as they are now, and their last results from the scheduler's own log
    foreach ($tn in @('MT5-AdoptRelease', 'QuantGuard-RunAs')) {
        try {
            $t = Get-ScheduledTask -TaskName $tn -ErrorAction Stop
            $i = $t | Get-ScheduledTaskInfo
            foreach ($a in $t.Actions) {
                Say ("task {0}: user={1} last={2:s} result=0x{3:X8} exe={4} wd={5} args={6}" -f $tn, $t.Principal.UserId,
                    $i.LastRunTime.ToUniversalTime(), [uint32]$i.LastTaskResult, $a.Execute, $a.WorkingDirectory, (Cut $a.Arguments 300))
                foreach ($m in [regex]::Matches("$($a.Arguments)", '"([A-Za-z]:\\[^"]+)"')) {
                    Say ("task {0}: path {1} exists={2}" -f $tn, $m.Groups[1].Value, (Test-Path -LiteralPath $m.Groups[1].Value))
                }
            }
        } catch { Say "task ${tn}: unreadable: $(Cut $_.Exception.Message)" }
    }

    # 2. the pinned adopter's own pre-log checks, re-run exactly as Adopt-And-Seal -Pinned runs them
    $tree = Join-Path $Adopt 'tree'
    $pinTxt = Join-Path $Adopt 'python.txt'
    foreach ($p in @($tree, (Join-Path $tree 'desks\mt5\scripts\Adopt-And-Seal.ps1'), $pinTxt, (Join-Path $Adopt 'venv'),
                     (Join-Path $tree 'ops\box_git\runas\git_acl.ps1'), (Join-Path $Adopt 'old_action.json'))) {
        Say ("adopt: {0} exists={1}" -f $p, (Test-Path -LiteralPath $p))
    }
    $py = $null
    try { $py = (Get-Content -LiteralPath $pinTxt -TotalCount 1 -ErrorAction Stop).Trim() } catch { Say "adopt: python.txt unreadable: $(Cut $_.Exception.Message)" }
    if ($py) {
        Say ("adopt: pinned python {0} exists={1}" -f $py, (Test-Path -LiteralPath $py))
        $saved = @{}
        $names = @('QUANT_ADOPT_PINNED', 'PYTHONPATH', 'PYTHONSAFEPATH', 'PYTHONNOUSERSITE', 'QUANT_LEDGER_ROOT',
                   'QUANT_PINNED_PYTHON', 'QUANT_GUARD_ROOT', 'GIT_CONFIG_PARAMETERS', 'PYTHONHOME', 'PYTHONSTARTUP')
        foreach ($n in $names) { $saved[$n] = [Environment]::GetEnvironmentVariable($n, 'Process') }
        try {
            $env:QUANT_ADOPT_PINNED = '1'; $env:PYTHONPATH = $tree; $env:PYTHONSAFEPATH = '1'; $env:PYTHONNOUSERSITE = '1'
            $env:QUANT_LEDGER_ROOT = $Live; $env:QUANT_PINNED_PYTHON = $py; $env:QUANT_GUARD_ROOT = $tree
            Remove-Item Env:PYTHONHOME, Env:PYTHONSTARTUP -ErrorAction SilentlyContinue
            $code = "import sys, json; print(json.dumps([bool(getattr(sys.flags, 'safe_path', False)) and bool(getattr(sys, '_quant_pinned_fence', False))] + sys.path))"
            $out = @(& $py -c $code 2>&1)
            $rc = $LASTEXITCODE
            Say ("adopt: probe rc={0} out={1}" -f $rc, (Cut (($out | ForEach-Object { "$_" }) -join ' | ') 1500))
            $sp = @(); try { $sp = @(ConvertFrom-Json -InputObject ((@($out | Where-Object { $_ -is [string] }) -join ''))) } catch { }
            $rootLow = $Live.TrimEnd('\').ToLowerInvariant() + '\'
            $leak = @($sp | Select-Object -Skip 1 | Where-Object { "$_" -eq '' -or ("$_".TrimEnd('\') + '\').ToLowerInvariant().StartsWith($rootLow) })
            Say ("adopt: probe verdict armed={0} leaks={1} -> {2}" -f ($sp.Count -ge 1 -and $sp[0] -eq $true), ($leak -join ', '),
                 $(if ($sp.Count -lt 1 -or $sp[0] -ne $true -or $leak.Count -gt 0) { 'WOULD EXIT 2 (not isolated)' } else { 'isolated' }))
        } catch { Say "adopt: probe failed: $(Cut $_.Exception.Message)" }
        finally { foreach ($n in $names) { [Environment]::SetEnvironmentVariable($n, $saved[$n], 'Process') } }
    }
    try {
        . (Join-Path $tree 'ops\box_git\runas\git_acl.ps1')
        $unsealed = @(Test-GitAclSealed -RepoRoot $Live)
        if ($unsealed.Count -gt 0) { Say ("adopt: git seal WOULD EXIT 2: " + (Cut ($unsealed -join '; ') 1500)) }
        else { Say 'adopt: git seal holds' }
    } catch { Say "adopt: git seal check failed: $(Cut $_.Exception.Message)" }

    # 3. the migrator: what its own files say (it writes migrate.log, state.json and ALARM.json itself)
    foreach ($p in @('python.txt', 'venues.json', 'runas_plan.py', 'runas_probe.py', 'git_acl.ps1', 'live_tree.txt', 'PINNED.json')) {
        Say ("runas: {0} exists={1}" -f $p, (Test-Path -LiteralPath (Join-Path $Runas $p)))
    }
    foreach ($p in @('state.json', 'ALARM.json')) {
        $f = Join-Path $Runas $p
        if (Test-Path -LiteralPath $f) {
            try { Say ("runas: {0} = {1}" -f $p, (Cut (Get-Content -LiteralPath $f -Raw) 600)) } catch { Say "runas: $p unreadable" }
        }
    }
    $ml = Join-Path $Runas 'migrate.log'
    if (Test-Path -LiteralPath $ml) {
        try { foreach ($l in @(Get-Content -LiteralPath $ml -Tail 25)) { Say ("runas: log | " + (Cut $l 400)) } } catch { Say 'runas: migrate.log unreadable' }
    } else { Say 'runas: migrate.log absent (it exits before its first Say)' }
    try {
        # the migrator's early statements, re-read the way it reads them (no python, no task change)
        $null = Get-Content -LiteralPath (Join-Path $Runas 'python.txt') -TotalCount 1 -ErrorAction Stop
        $null = Get-Content -LiteralPath (Join-Path $Adopt 'python.txt') -TotalCount 1 -ErrorAction Stop
        $null = Get-Content -LiteralPath (Join-Path $Runas 'venues.json') -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        Say 'runas: early reads pass (python.txt, adopt\python.txt, venues.json)'
    } catch { Say "runas: early read fails: $(Cut $_.Exception.Message)" }

    # 4. the scheduler's own record of the last runs (event 201 carries the action's exit code)
    try {
        $ev = Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-TaskScheduler/Operational'; Id = 201; StartTime = (Get-Date).AddHours(-2) } -MaxEvents 400 -ErrorAction Stop |
            Where-Object { $_.Message -match 'MT5-AdoptRelease|QuantGuard-RunAs' } | Select-Object -First 6
        foreach ($e in $ev) { Say ("event 201 {0:s}: {1}" -f $e.TimeCreated.ToUniversalTime(), (Cut $e.Message 300)) }
    } catch { Say "events: unreadable: $(Cut $_.Exception.Message)" }

    Say 'guardian status end'
}

# ---- PHASE 3: OUTPUT-BASED HEALTH (zuck R2, 2026-11-27 16:59Z; Audit pre-read 21:52Z) --------
# A task is healthy only when its declared output is fresh. Exit codes, Running states and
# heartbeats are ignored. Declarations come from ops/box_git/guardian/task_outputs.json at the
# CURRENT BOOT (read from boot-src with git show, never from a file anyone else can write), so
# every change to what SYSTEM may restart is a TRUST change (Audit + the 10-minute veto).
# Bounds (Audit 21:52Z), enforced here and pinned by tests:
#   * exact task names only; a disabled task is reported, never enabled; no principal, action,
#     trigger or setting is ever touched -- only Start-ScheduledTask, and never Stop (MF1: an
#     output mtime under C:\opt\quant is writable by adopted code, so "stale" is never a reason
#     to kill anything). A RUNNING task with stale output is HUNG: alarm only;
#   * a row restarts only when its restart is exactly 'auto' or 'auto_dead_only', it has outputs,
#     its live action is exactly the declared one, the action passes the fail-closed money test
#     (Test-MoneyAction), and it is not a box-acting task (MF2/MF3); everything else is alarm;
#   * the guard's own tasks and the movers are alarm-only whatever the JSON says;
#   * nothing starts or stops while the run-as migrator is mid-cutover or running;
#   * one restart per task per max-age window, one restart per pass, two restarts that did not
#     move the output escalate the row to ALARM and it is never restarted again by this script;
#   * GatewayResident ('auto_dead_only'): Start only, outside the broker rollover hour, and only
#     when its task is not running and no gateway python process is alive (MF4: matched by command
#     line through CIM; an unreadable process table means alive).
$NeverRestart = @('QuantGuard-RunAs', 'QuantForge-BootMove', 'QuantForge-Pin', 'MT5-AdoptRelease', 'QuantForge-Loop',
    'MT5-RebootDrill', 'MT5-ReapGitWriters', 'MT5-ClockFixer', 'MT5-ProcessHealth', 'MT5-Healers', 'MT5-IdentityHealer',
    'MT5-PlumbingWatchdog', 'MT5-MoatRecorder-Watchdog', 'MT5-FetchUniverse-Repair', 'MT5-SshGuard', 'Quant-CpuShaper',
    'Claude-Bridge-Watchdog', 'Quant-SignTrain')
# replay_shadow.MONEY_PATH and ENTRY_POINTS (a test pins these to that file), plus its MONEY_WORDS
$MoneyPrefixes = @('desks/mt5/mt5desk/', 'desks/mt5/prop/', 'desks/mt5/data/', 'desks/mt5/scripts/',
    'desks/mt5/ops/', 'data/', 'libs/execution/', 'libs/risk/', 'libs/portfolio/')
$MoneyEntries = @('desks/mt5/research/run_gateway_loop.py', 'desks/mt5/research/gateway_resident.py',
    'desks/mt5/research/pf_allocator.py', 'desks/mt5/proposals/fusion_deadman.py',
    'desks/mt5/prop/e8_executor.py', 'desks/mt5/prop/e8_gold.py', 'desks/mt5/prop/e8_book.py',
    'desks/mt5/prop/ftmo_follower.py')
$MoneyWords = 'terminal64|metatrader|autotrading|mt5[-_]?gateway|ftmo|fusion|(?<![a-z0-9])e8(?![0-9])|order_send|order_check|positions_get'
function Get-BootFile([string] $rel) {
    # the ONLY git in this file: `git show` of one of two committed files at the current boot
    if (@('ops/box_git/guardian/task_outputs.json', 'ops/money_closure.txt') -notcontains $rel) { throw "box_guardian: $rel is not a boot file it reads" }
    $boot = "$((Get-Content -Raw -LiteralPath (Join-Path $Forge 'loop.json') | ConvertFrom-Json).boot)".Trim()
    if ($boot -notmatch '^[0-9a-f]{40}$') { return $null }
    $src = Join-Path $Forge 'boot-src'
    $raw = @(& git -c safe.directory=* -c core.hooksPath=NUL -c core.fsmonitor=false -C $src show "${boot}:$rel" 2>$null)
    if ($LASTEXITCODE) { return $null }
    return ($raw -join "`n")
}
function Get-Declarations {
    try {
        $j = Get-BootFile 'ops/box_git/guardian/task_outputs.json'
        if (-not $j) { return $null }
        return ($j | ConvertFrom-Json)
    } catch { return $null }
}
function Get-ActionText($t) {
    # the same text the declarations carry: Execute|Arguments|WorkingDirectory per action, runs of
    # five or more digits replaced by <N> (no account login is ever written down)
    $parts = foreach ($a in @($t.Actions)) { "{0}|{1}|{2}" -f $a.Execute, $a.Arguments, $a.WorkingDirectory }
    return ((@($parts) -join ' || ') -replace '\d{5,}', '<N>')
}
function Get-ActionHash([string] $text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return (($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text)) | ForEach-Object { $_.ToString('x2') }) -join '') }
    finally { $sha.Dispose() }
}
function Test-MoneyAction([string] $text, $scripts, $closure) {
    # FAIL CLOSED: true unless the live action names no venue word and every script it runs (the
    # declared, hash-matched list) is a repository .py file off the money path. The test rebuilds
    # the declared money_path from the import closure; this is the runtime floor under it.
    if ($text -match $MoneyWords) { return $true }
    $all = @($scripts | Where-Object { $_ })
    if (-not $all.Count) { return $true }
    foreach ($s in $all) {
        $r = "$s".ToLowerInvariant()
        if ($r -notmatch '^[a-z0-9_][a-z0-9_./-]*\.py$' -or $r.Contains('..')) { return $true }
        if ($MoneyEntries -contains $r -or $closure -contains $r) { return $true }
        foreach ($pfx in $MoneyPrefixes) { if ($r.StartsWith($pfx)) { return $true } }
    }
    return $false
}
function Test-GatewayAlive {
    # MF4: a detached gateway outlives its task, so the process table decides, by command line
    try {
        $ps = @(Get-CimInstance -ClassName Win32_Process -Filter "Name LIKE 'python%'" -OperationTimeoutSec 20 -ErrorAction Stop)
        foreach ($p in $ps) {
            if ($null -eq $p.CommandLine) { return $true }
            if ($p.CommandLine -match 'gateway_resident|run_gateway_loop') { return $true }
        }
        return $false
    } catch { return $true }
}
function Get-NewestOutput($row) {
    $newest = $null
    foreach ($g in @($row.outputs)) {
        if (-not $g) { continue }
        try {
            foreach ($f in @(Get-ChildItem -Path $g -File -Force -ErrorAction SilentlyContinue)) {
                if (-not $newest -or $f.LastWriteTimeUtc -gt $newest) { $newest = $f.LastWriteTimeUtc }
            }
        } catch { }
    }
    return $newest
}
function Get-BrokerHour {
    # broker clock = New York + 7 h (the venue's own server time)
    $ny = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date).ToUniversalTime(), 'Eastern Standard Time')
    return $ny.AddHours(7).Hour
}
function Test-RunasBusy {
    try {
        $t = Get-ScheduledTask -TaskName 'QuantGuard-RunAs' -ErrorAction Stop
        if ("$($t.State)" -eq 'Running') { return $true }
    } catch { }
    try {
        $st = Get-Content -Raw -LiteralPath (Join-Path $Runas 'state.json') -ErrorAction Stop | ConvertFrom-Json
        if (@('WAIT_WINDOW', 'MOVED', 'WATCH') -contains "$($st.state)") { return $true }
    } catch { }
    return $false
}
function Start-Declared([string] $name) {
    # THE ONLY TASK CONTROL IN THIS FILE: exact name, Start only, and only a task that is not running
    if ($NeverRestart -contains $name -or $name -like 'QuantGuard-*') { throw "box_guardian: $name is alarm-only" }
    if ("$((Get-ScheduledTask -TaskName $name -ErrorAction Stop).State)" -ne 'Ready') { throw "box_guardian: $name is not Ready" }
    Start-ScheduledTask -TaskName $name -ErrorAction Stop
}
function Invoke-Health {
    $decl = Get-Declarations
    $now = (Get-Date).ToUniversalTime()
    $prev = @{}
    if ((Test-Path -LiteralPath $Health) -and (Test-AdminFile $Health)) {
        try { foreach ($r in @((Get-Content -Raw -LiteralPath $Health | ConvertFrom-Json).rows)) { $prev["$($r.task)"] = $r } } catch { }
    }
    $byName = @{}
    if ($decl) { foreach ($r in @($decl.tasks)) { $byName["$($r.task)"] = $r } }
    $closure = @()
    try { $closure = @(((Get-BootFile 'ops/money_closure.txt') -split "`n") | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ -and -not $_.StartsWith('#') }) } catch { }
    $busy = Test-RunasBusy
    $restartedThisPass = $false
    $rows = @()
    $tasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
        $_.TaskName -match '^(MT5-|Quant|E8-|Claude-Bridge|Codex-)' })
    foreach ($t in $tasks) {
        $name = "$($t.TaskName)"
        $d = $byName[$name]
        $p = $prev[$name]
        $row = [ordered]@{ task = $name; state = "$($t.State)"; verdict = ''; newest_output = $null; age_min = $null
                           max_age_min = $null; restart = ''; last_restart = $null; restart_out = $null; fails = 0; action = ''
                           action_text = ''; action_sha256 = '' }
        $live = Get-ActionText $t
        $row.action_text = $live; $row.action_sha256 = Get-ActionHash $live
        if ($p) { $row.last_restart = $p.last_restart; $row.restart_out = $p.restart_out; $row.fails = [int]$p.fails }
        if (-not $d -or -not @($d.outputs | Where-Object { $_ }).Count) {
            $row.verdict = 'UNDECLARED'; $rows += [pscustomobject]$row; continue
        }
        $row.max_age_min = $d.max_age_min
        # MF2/MF3: alarm is the default; a row earns a restart mode only by passing every test here
        $mode = "$($d.restart)"
        if (@('auto', 'auto_dead_only') -notcontains $mode) { $mode = 'alarm' }
        elseif ($NeverRestart -contains $name -or $name -like 'QuantGuard-*') { $mode = 'alarm' }
        elseif ($d.money_path -and $name -ne 'MT5-GatewayResident') { $mode = 'alarm' }
        elseif ("$($d.action_sha256)" -ne $row.action_sha256) { $mode = 'alarm'; $row.action = 'none: live action differs from the declared one' }
        elseif ($mode -eq 'auto' -and (Test-MoneyAction $live @($d.action_scripts) $closure)) { $mode = 'alarm' }
        elseif ($mode -eq 'auto_dead_only' -and $name -ne 'MT5-GatewayResident') { $mode = 'alarm' }
        $row.restart = $mode
        $newest = Get-NewestOutput $d
        if ($newest) { $row.newest_output = $newest.ToString('s'); $row.age_min = [math]::Round(($now - $newest).TotalMinutes, 1) }
        # did the last restart move the output?
        if ($row.last_restart -and $null -ne $row.restart_out) {
            $lr = [datetime]::Parse("$($row.last_restart)", [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
            if ($newest -and "$($row.restart_out)" -ne $newest.ToString('s')) { $row.fails = 0; $row.last_restart = $null; $row.restart_out = $null }
            elseif ($d.max_age_min -and ($now - $lr).TotalMinutes -gt [double]$d.max_age_min) { $row.fails = [int]$row.fails + 1; $row.last_restart = $null }
        }
        if ("$($t.State)" -eq 'Disabled') { $row.verdict = 'DISABLED' }
        elseif (-not $d.max_age_min) { $row.verdict = if ($newest) { 'NOT_PERIODIC' } else { 'NO_OUTPUT_YET' } }
        elseif (-not $newest) { $row.verdict = 'NO_OUTPUT_YET' }
        elseif ($row.age_min -le [double]$d.max_age_min) { $row.verdict = 'FRESH'; $row.fails = 0 }
        elseif ([int]$row.fails -ge 2) { $row.verdict = 'ALARM' }
        else { $row.verdict = 'STALE' }
        if ($row.verdict -eq 'STALE' -and "$($t.State)" -eq 'Running') { $row.verdict = 'HUNG' }
        if ($row.verdict -eq 'STALE' -and -not $row.last_restart) {
            $why = $null
            if ($mode -eq 'alarm') { $why = 'alarm-only' }
            elseif ("$($t.State)" -ne 'Ready') { $why = "task is $($t.State)" }
            elseif ($busy) { $why = 'run-as migrator busy' }
            elseif ($restartedThisPass) { $why = 'one restart per pass' }
            elseif ($mode -eq 'auto_dead_only' -and (Get-BrokerHour) -eq 0) { $why = 'broker rollover hour' }
            elseif ($mode -eq 'auto_dead_only' -and (Test-GatewayAlive)) { $why = 'a gateway process is alive: alarm only' }
            if ($why) { if (-not $row.action) { $row.action = "none: $why" } }
            else {
                try {
                    Start-Declared $name
                    $restartedThisPass = $true
                    $row.last_restart = $now.ToString('s'); $row.restart_out = $row.newest_output
                    $row.action = 'started'
                    Say ("health: {0} output {1} min old (max {2}) -> {3}" -f $name, $row.age_min, $d.max_age_min, $row.action)
                } catch { $row.action = "restart failed: $(Cut $_.Exception.Message 200)" }
            }
        }
        $rows += [pscustomobject]$row
    }
    $counts = [ordered]@{}
    foreach ($v in @('FRESH', 'STALE', 'HUNG', 'ALARM', 'UNDECLARED', 'NO_OUTPUT_YET', 'NOT_PERIODIC', 'DISABLED')) {
        $counts[$v] = @($rows | Where-Object { $_.verdict -eq $v }).Count
    }
    $doc = [ordered]@{ generated_at = $now.ToString('s'); declarations = [bool]$decl; runas_busy = $busy
                       tasks = $rows.Count; counts = $counts; rows = $rows }
    Write-Status $Health ($doc | ConvertTo-Json -Depth 5)
}

if ($doStatus) { Invoke-Status }
try { Invoke-Health } catch { Say "health: failed: $(Cut $_.Exception.Message)" }
exit 0
