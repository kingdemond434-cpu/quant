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
      * It WRITES exactly one file: C:\ProgramData\QuantBox\logs\guard_status.log (append only,
        through Write-Status, which refuses any other path). Nothing else, ever: not trust\,
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
#>
$ErrorActionPreference = 'Continue'
$Q      = 'C:\ProgramData\QuantBox'
$Guard  = Join-Path $Q 'guard'
$Adopt  = Join-Path $Guard 'adopt'
$Runas  = Join-Path $Guard 'runas'
$Live   = 'C:\opt\quant'
$LogDir = Join-Path $Q 'logs'
$Status = Join-Path $LogDir 'guard_status.log'

function Test-PlainFile([string] $p) {
    # SYSTEM must never write through a link a non-admin planted: no reparse point on the folder
    # or the file, and exactly one hard link to the file.
    if ((Get-Item -LiteralPath $LogDir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
    if (-not (Test-Path -LiteralPath $p)) { return $true }
    if ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
    $links = @(& "$env:SystemRoot\System32\fsutil.exe" hardlink list $p 2>$null)
    return (-not $LASTEXITCODE) -and $links.Count -eq 1
}
function Write-Status([string] $path, [string] $line) {
    # THE ONLY WRITE IN THIS FILE. Any other target is refused, so a later edit cannot widen it
    # without changing this guard (and the test that pins it).
    if ($path -ne $Status) { throw "box_guardian: refused to write $path (only $Status)" }
    if (-not (Test-Path -LiteralPath $LogDir -PathType Container)) { return }
    if (-not (Test-PlainFile $Status)) { return }
    if (-not (Test-Path -LiteralPath $Status)) {
        # created once, with its own ACL and no inheritance: SYSTEM and Administrators full,
        # Users read. This is the only ACL this script ever sets, and only on its own new file.
        $fs = New-Object Security.AccessControl.FileSecurity
        $fs.SetAccessRuleProtection($true, $false)
        foreach ($r in @(@('S-1-5-18', 'FullControl'), @('S-1-5-32-544', 'FullControl'), @('S-1-5-32-545', 'Read'))) {
            $fs.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
                (New-Object Security.Principal.SecurityIdentifier($r[0])), $r[1], 'Allow')))
        }
        $fs.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))
        $h = [IO.File]::Create($Status, 4096, [IO.FileOptions]::None, $fs); $h.Dispose()
    }
    $row = '{0}  {1}' -f (Get-Date).ToUniversalTime().ToString('s'), $line
    [IO.File]::AppendAllText($Status, $row + "`r`n", (New-Object Text.UTF8Encoding($false)))
}
function Say([string] $m) { Write-Status $Status $m }
function Cut([string] $s, [int] $n = 400) {
    $s = "$s" -replace '\s+', ' '
    if ($s.Length -gt $n) { return $s.Substring(0, $n) + '...' }
    return $s
}

# Once an hour is enough to diagnose; the mover runs this every 5 minutes. The hour is read from
# the log itself (its last 'guardian status' line), so no second file is ever written.
try {
    if (Test-Path -LiteralPath $Status) {
        $last = Get-Content -LiteralPath $Status -Tail 400 | Where-Object { $_ -match '^\S+  guardian status begin' } | Select-Object -Last 1
        if ($last) {
            $at = [datetime]::Parse(($last -split '  ')[0], [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
            if (((Get-Date).ToUniversalTime() - $at).TotalMinutes -lt 55) { exit 0 }
        }
    }
} catch { }

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
exit 0
