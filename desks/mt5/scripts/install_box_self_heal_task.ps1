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
#   ... install_box_self_heal_task.ps1 -RepoRoot C:\path\to\quant   (the source repo, explicitly)
param([switch]$IfMissing, [string]$RepoRoot = '')

$ErrorActionPreference = 'Stop'

$TaskName = 'Quant-BoxSelfHeal'
if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    "{0} already registered; -IfMissing: nothing to do" -f $TaskName
    return
}
# THE SOURCE REPO IS EXPLICIT (v4 must-fix 2): -RepoRoot, or the repo this script sits in; either
# way git must confirm it is a work tree's top level, and every copied file is read from ITS HEAD.
if (-not $RepoRoot) { $RepoRoot = Join-Path $PSScriptRoot '..\..\..' }
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
if (-not $Git) { throw "git.exe is not on PATH: the copied files are read from the committed blobs with git; not installing" }
$top = (& $Git -C $RepoRoot rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $top) { throw "$RepoRoot is not a git work tree (git rev-parse failed); not installing" }
if ((Resolve-Path -LiteralPath $top).Path -ne $RepoRoot) { throw "$RepoRoot is not the top of its work tree ($top); pass -RepoRoot <repo root>" }
"source repo: {0}" -f $RepoRoot

# THE SYSTEM TASK RUNS AN ADMIN-ONLY COPY, NEVER THE REPO TREE (audit HOLD of 7a01c1b09). The repo
# is writable by the non-elevated bridge and every cloud session; a SYSTEM task that executed a
# file from it would run whatever was last written there with SYSTEM's rights. So this file and
# the only two helpers it loads are copied into C:\ProgramData\QuantBox\bin, under
# install_unattended.ps1's audited ACL (owned by Administrators/SYSTEM, no junction anywhere, no
# ACE that grants anyone else more than read), and the task runs THAT copy. The installed copy
# loads its helpers from beside itself only; the repo (named in bin\box_self_heal.root) is only
# where it writes its report. Re-run this installer to deploy a new version.
$Root   = 'C:\ProgramData\QuantBox'
$BinDir = Join-Path $Root 'bin'
# WHAT THE WATCHDOG DECIDES FROM LIVES HERE, NOT IN THE REPO (audit HOLD of 5b3504f50). The bridge
# and every agent session can write the repo, so a cross-pass state there could plant an orphan
# target, a STALLED CPU baseline, a dead-owner clock or a reset attempt cap. The state and the
# attempt ledger live in this admin-only directory; the pass refuses to act unless its ACL is
# provably Administrators/SYSTEM only. Only the report (which nothing reads back to decide) is
# published into the repo.
$StateDir = Join-Path $Root 'state'
# EACH COPIED FILE IS PINNED TO THE sha256 OF ITS COMMITTED BLOB (audit HOLD of 5b3504f50), AND
# IS WRITTEN FROM THAT BLOB, NOT FROM THE WORKING TREE (v4 must-fix 2). The box checks out with
# core.autocrlf, and these three files are outside desks/mt5/.gitattributes (eol=lf), so their
# working-tree bytes are CRLF and never match a pin of the LF blob. `git cat-file blob HEAD:<path>`
# is the raw committed bytes, with no eol or filter conversion; a session that swaps the working
# tree changes nothing it reads. The destination is then hashed against the pin, which
# `tests/ops/test_box_self_heal.py` asserts equals the blob at HEAD so it cannot drift. Regenerate
# after any change to a copied file:
#   git show HEAD:ops/box_self_heal.py | sha256sum   (and the other two)
$Pins = [ordered]@{
    'box_self_heal.py' = @{ src = 'ops/box_self_heal.py';       sha256 = 'da87e34e4c93cd96fd2e2f0834426bb1718871f25ef5cd3870631cde615359d7' }
    'process_health.py' = @{ src = 'ops/process_health.py';      sha256 = '1e989e2e942f69d21f0827d2702d579e2d152c4b600b608d49f7ca7681647f8e' }
    'alert_channels.py' = @{ src = 'libs/ops/alert_channels.py'; sha256 = '4448f782dfa7dc4ec0aecd1dc71145403d3de1d1dcbb9c64e81cf95be3e5f4b5' }
}

function Save-GitBlob([string] $rel, [string] $dst) {
    # The committed bytes of HEAD:<rel>, copied raw from git's stdout into a NEW file: never a
    # PowerShell pipeline (it re-encodes text), never the working-tree file.
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Git
    $psi.Arguments = ('-C "{0}" cat-file blob "HEAD:{1}"' -f $RepoRoot, $rel)
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $err = $proc.StandardError.ReadToEndAsync()
    $fs = [System.IO.File]::Open($dst, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    try { $proc.StandardOutput.BaseStream.CopyTo($fs) } finally { $fs.Dispose() }
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) {
        Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
        throw "git cat-file blob HEAD:$rel failed in $RepoRoot (rc $($proc.ExitCode): $($err.Result.Trim())); the blob is missing -- not installing"
    }
}
$Installed = Join-Path $BinDir 'box_self_heal.py'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { throw "run this elevated: registering a SYSTEM task needs an administrator" }

$adm = 'S-1-5-32-544'; $sys = 'S-1-5-18'; $usr = 'S-1-5-32-545'
# A FOLDER WHOSE CODE THE SYSTEM TASK RUNS (the interpreter's) IS JUDGED THE WAY
# ops/bridge/bridge_watchdog.ps1's Get-AclProblem judges its own folders (v5 MF-B): a stock
# C:\Program Files\Python314\Lib carries TrustedInstaller, CREATOR OWNER (InheritOnly) and ALL
# APPLICATION PACKAGES (read/execute), and the v4 check refused every SID it did not list. Now, as in
# the bridge: the owner must be Administrators, SYSTEM or TrustedInstaller; Administrators, SYSTEM
# and TrustedInstaller may hold anything; an InheritOnly ACE does not apply to the folder itself and
# is skipped; any OTHER SID that holds a write-class right fails. Read and execute are not refused.
$AdminSids = @("S-1-5-32-544", "S-1-5-18", "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464")
$WriteMask = [int64]([System.Security.AccessControl.FileSystemRights]"Write, Delete, DeleteSubdirectoriesAndFiles, ChangePermissions, TakeOwnership") -bor 0x50000000
function Test-DirAdminOnly([string] $dir) {
    if (-not (Test-Path -LiteralPath $dir)) { return "absent" }
    if ((Get-Item -LiteralPath $dir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return "a junction or symlink" }
    $acl = Get-Acl -LiteralPath $dir -ErrorAction Stop
    $owner = (New-Object System.Security.Principal.NTAccount($acl.Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($owner -notin $AdminSids) { return "$dir is owned by $($acl.Owner)" }
    foreach ($a in $acl.Access) {
        if ($a.AccessControlType -ne "Allow") { continue }
        if ($a.PropagationFlags -band [System.Security.AccessControl.PropagationFlags]::InheritOnly) { continue }
        $sid = try { $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { [string]$a.IdentityReference }
        if ($sid -in $AdminSids) { continue }
        if (([int64]$a.FileSystemRights -band $WriteMask) -ne 0) { return "$dir grants $($a.FileSystemRights) to $($a.IdentityReference)" }
    }
    return $null
}

# A PATH python.exe IS ONLY TRUSTED FROM AN ADMIN-ONLY DIRECTORY (audit should-fix of 5b3504f50):
# a SYSTEM task that ran a python a non-admin could replace would run their code as SYSTEM. Prefer
# the known Program Files interpreter; fall back to PATH only when its own directory is admin-only.
# Not only the exe's folder (v4 should-fix 7): the stdlib (Lib), the third-party packages
# (Lib\site-packages, where psutil lives) and DLLs are code the SYSTEM task imports, so each must be
# admin-only too, whichever interpreter is chosen. (-I already drops the user site and PYTHONPATH.)
$Python = 'C:\Program Files\Python314\python.exe'
if (-not (Test-Path $Python)) {
    $cand = (Get-Command python.exe -ErrorAction Stop).Source
    $why = Test-DirAdminOnly (Split-Path -Parent $cand)
    if ($why) { throw "refusing PATH python at ${cand}: its directory is not admin-only ($why); install Python to C:\Program Files or fix its ACL" }
    $Python = $cand
}
$PyHome = Split-Path -Parent $Python
foreach ($sub in @('Lib', 'Lib\site-packages', 'DLLs')) {
    $d = Join-Path $PyHome $sub
    if ($sub -eq 'DLLs' -and -not (Test-Path -LiteralPath $d)) { continue }
    $why = Test-DirAdminOnly $d
    if ($why) { throw "refusing python at ${Python}: $d is not admin-only ($why); a non-admin could plant code the SYSTEM task imports" }
}
# A native command's stderr under ErrorActionPreference=Stop is a terminating NativeCommandError on
# Windows PowerShell 5.1 (v5 should-fix 2): probe with a local Continue, then read the exit code.
& {
    $ErrorActionPreference = 'Continue'
    & $Python -I -c "import psutil" 2>$null | Out-Null
}
if ($LASTEXITCODE -ne 0) {
    "WARNING: psutil is not importable by $Python; the watchdog will report UNMEASURED (RED) and stop nothing until it is"
}
# THE ROOT IS ADMIN-ONLY FROM ITS FIRST BYTE (install_unattended.ps1's pattern, verbatim in effect):
# a new root is created with its locked ACL in one call; an existing one that Administrators/SYSTEM
# do not own is refused, never taken over; no junction is followed anywhere under it.
if (-not (Test-Path -LiteralPath $Root)) {
    $sec = New-Object System.Security.AccessControl.DirectorySecurity
    $sec.SetAccessRuleProtection($true, $false)
    $sec.SetOwner((New-Object System.Security.Principal.SecurityIdentifier $adm))
    foreach ($ace in @(@($adm, 'FullControl'), @($sys, 'FullControl'), @($usr, 'ReadAndExecute'))) {
        $sec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier $ace[0]), $ace[1], 'ContainerInherit, ObjectInherit', 'None', 'Allow')))
    }
    $null = [System.IO.Directory]::CreateDirectory($Root, $sec)
}
$owner = (New-Object System.Security.Principal.NTAccount((Get-Acl -LiteralPath $Root).Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
if ($owner -notin @($adm, $sys)) { throw "$Root is owned by $owner, not Administrators/SYSTEM; delete it as an administrator and re-run" }
foreach ($c in @(Get-Item -LiteralPath $Root -Force) + @(Get-ChildItem -LiteralPath $Root -Force -Recurse)) {
    if ($c.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "$($c.FullName) is a junction or symlink; not installing" }
}
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
# THE SYSTEM TASK'S LOG IS ADMIN-ONLY TOO (v5 MF-C): cmd.exe appends to it as SYSTEM, and a log in
# the repo's desks\mt5\logs could be a junction that redirects that write.
$LogDir = Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir 'Quant-BoxSelfHeal.log'
function Assert-AdminOnly {
    foreach ($path in @($Root) + @(Get-ChildItem -LiteralPath $Root -Force -Recurse | ForEach-Object { $_.FullName })) {
        foreach ($a in (Get-Acl -LiteralPath $path).Access | Where-Object { $_.AccessControlType -eq 'Allow' }) {
            $sid = $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
            $write = [int64]$a.FileSystemRights -band ([int64][System.Security.AccessControl.FileSystemRights]"Write, Delete, ChangePermissions, TakeOwnership" -bor 0x50000000)
            if ($sid -notin @($adm, $sys, $usr) -or ($sid -eq $usr -and $write -ne 0)) {
                throw "$path grants $($a.IdentityReference) more than read; not installing"
            }
        }
    }
}
Assert-AdminOnly
foreach ($name in $Pins.Keys) {
    $rel = $Pins[$name].src; $pin = $Pins[$name].sha256.ToLower(); $dst = Join-Path $BinDir $name
    Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
    Save-GitBlob $rel $dst
    $dstHash = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash.ToLower()
    if ($dstHash -ne $pin) {
        Remove-Item -LiteralPath $dst -Force -ErrorAction SilentlyContinue
        throw "HEAD:$rel in $RepoRoot has sha256 $dstHash, not its pinned $pin; HEAD is not the reviewed file -- not installing"
    }
    "installed {0} from HEAD:{1} (sha256 {2})" -f $dst, $rel, $pin.Substring(0, 12)
}

# THE REPO ROOT IS WRITTEN HERE, NOT TAKEN FROM THE WORKING DIRECTORY (v5 MF-A). The installed copy
# reads it from this admin-only file (else C:\opt\quant); the task runs in the state folder.
[System.IO.File]::WriteAllText((Join-Path $BinDir 'box_self_heal.root'), $RepoRoot)

# THE ALERT CONFIG SYSTEM READS IS THE ADMIN'S INSTALL-TIME COPY (v5 should-fix 3). The repo's
# data\secrets is writable by the bridge and every session, so SYSTEM never reads it: this copies
# alert_channels.json (and heartbeat_url.json) into the state folder with an Administrators/SYSTEM-
# only ACL (secrets: not even Users may read them). The watchdog opens only https channels from it.
# Re-run this installer after changing the channels.
foreach ($n in @('alert_channels.json', 'heartbeat_url.json')) {
    $s = Join-Path $RepoRoot (Join-Path 'data\secrets' $n); $d = Join-Path $StateDir $n
    Remove-Item -LiteralPath $d -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $s)) { "WARNING: no {0}: the watchdog's pages are NOT-ARMED until it exists and this is re-run" -f $s; continue }
    if ((Get-Item -LiteralPath $s -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "$s is a junction or symlink; not installing" }
    [System.IO.File]::WriteAllBytes($d, [System.IO.File]::ReadAllBytes($s))
    $fsec = New-Object System.Security.AccessControl.FileSecurity
    $fsec.SetAccessRuleProtection($true, $false)
    $fsec.SetOwner((New-Object System.Security.Principal.SecurityIdentifier $adm))
    foreach ($sidv in @($adm, $sys)) {
        $fsec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier $sidv), 'FullControl', 'Allow')))
    }
    Set-Acl -LiteralPath $d -AclObject $fsec
    "alert config: copied {0} -> {1} (Administrators/SYSTEM only)" -f $s, $d
}
Assert-AdminOnly     # the copies, root file, log and state dir; proved, not assumed

# No arguments: the rule table is in the code, and the only flag it has is --dry-run. The
# INSTALLED copy, isolated (-I: no PYTHONPATH, no user site, no script-dir imports). cmd.exe by its
# absolute System32 path, and the WORKING DIRECTORY IS THE ADMIN-ONLY STATE FOLDER, never the repo
# (v5 MF-A): CreateProcess searches the current directory first, so a repo working directory would
# let a planted schtasks.exe or python.exe there run as SYSTEM.
$Cmd = Join-Path ([Environment]::SystemDirectory) 'cmd.exe'
$action = New-ScheduledTaskAction -Execute $Cmd -WorkingDirectory $StateDir -Argument `
    ('/d /s /c ""{0}" -I -W ignore "{1}" >> "{2}" 2>&1"' -f $Python, $Installed, $Log)

# A DAILY trigger repeating every five minutes for one day, never a long -Once (one expired on
# this box 2026-09-21 with Next Run Time N/A). Offset to :03 so it misses the :05/:12/:20 writers.
$at = (Get-Date).Date.AddMinutes(3)
$trigger = New-ScheduledTaskTrigger -Daily -At $at
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $at `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# FIFTEEN MINUTES, NOT FOUR (audit HOLD of 7a01c1b09). The scheduler kills a task at its limit
# with no chance to run a `finally`, so a limit that can land inside a freeze leaves a tree
# SUSPENDED -- a wedge this watchdog made. The worst pass is five 60 s schtasks calls (query,
# end, end, end, run; schtasks has been measured hanging past two minutes on this box under
# load), two 10 s kill waits and a 12 s-per-channel page: about 6.5 min. Fifteen is over twice
# that, and still under the report's 20 min staleness, so a hung pass still reads RED.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew

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
    -Description "Closed self-heal table (C:\ProgramData\QuantBox\bin\box_self_heal.py, copied from ops\box_self_heal.py): a hung MT5-IndependenceIntake, a wedged or dead Quant-WorkflowGate only; never the terminal, the money path, the bridge or the miners. Every act and refusal is RED in reports\BOX_SELF_HEAL.json." | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
"installed {0}: state={1} user={2} interval={3}" -f $t.TaskName, $t.State, $t.Principal.UserId, $t.Triggers[0].Repetition.Interval

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 20
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"started {0}: state={1} last_run={2} last_result={3}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult
"report: desks\mt5\reports\BOX_SELF_HEAL.json; state + ledger: {0} (admin-only); log: {1}" -f $StateDir, $Log
