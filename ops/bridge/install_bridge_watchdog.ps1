# REGISTER THE BOX BRIDGE'S WATCHDOG, AND START IT NOW (2026-10-28).
#
# The bridge (`claude remote-control` in C:\opt\bridge\quant) was started by hand in the RDP
# session and died minutes later; nothing brought it back but zuck. This registers ONE task,
# Claude-Bridge-Watchdog, that runs ops\bridge\bridge_watchdog.ps1 at this user's logon and
# re-arms it every five minutes (the watchdog's own mutex makes a re-arm a no-op while it lives).
# The watchdog keeps the server running and restarts it whenever it exits.
#
# WHY A COPY OUTSIDE THE CHECKOUT. Sessions on the bridge check out branches in C:\opt\bridge\quant.
# The task runs C:\ProgramData\ClaudeBridge\bin\bridge_watchdog.ps1, copied there, so a branch
# switch in the checkout never changes or removes the script that keeps the bridge alive. Re-run
# this installer to update it.
#
# WHY C:\ProgramData (audit v1.2). A folder an administrator creates under C:\ inherits Modify for
# Authenticated Users, so anyone could RENAME C:\opt\bridge and plant a bin of their own that the
# elevated task would then run -- the pin check lives in the very script they replaced. Under
# C:\ProgramData nobody but administrators may rename or re-permission what an administrator
# created, and the watchdog refuses to run when any folder above bin or logs says otherwise.
#
# THE CHECKOUT (C:\opt\bridge\quant) is locked too unless -SkipCheckoutLock: the elevated sessions
# run in it and load its hooks. Its DACL becomes Administrators + SYSTEM full, Users read. Its owner
# (the folder and its .git, not every file) becomes the user installing this, who is the user the
# bridge runs as: git refuses a repository owned by anyone else, BUILTIN\Administrators included
# (2026-10-28: every worktree session parked on "dubious ownership"). No git config is written. What sits above it (C:\opt) is not
# touched here -- it also holds the live desk -- so a C:\opt that Authenticated Users may modify
# still lets a non-admin rename the checkout away; bridge_status.ps1 reports that as
# LIVE_CHECKOUT_AT_RISK. Measure first: `icacls C:\opt` and `Get-LocalUser` / `net localgroup
# Administrators` -- on a box whose only accounts are administrators there is nobody to escalate.
#
# WHY INTERACTIVE, AND WHAT A REBOOT STILL NEEDS. The server uses this user's Claude sign-in and the
# FTMO terminal already needs this user's desktop session, so the task runs as this user,
# interactive, at the run level the bridge runs at today (elevated Administrator). After a reboot
# the bridge comes back at the first logon of this user (one RDP connect + Disconnect, which the
# FTMO terminal needs anyway). Coming back with nobody logged on would need Windows auto-logon,
# which stores this account's password on the box; that is not done here.
#
# BOOT START WITH NOBODY LOGGED ON: -AtStartup (2026-11-13, zuck: "box keeps its Claude Remote
# Control session alive on its own: start at boot, run under a watchdog, restart when it dies,
# legitimate auto-start only, no credential workarounds"). Windows offers exactly one way to run a
# task as a named user before anyone logs on WITHOUT storing that user's password: the S4U logon
# type ("Run whether user is logged on or not" + "Do not store password"). Task Scheduler asks the
# domain/LSA for a token for the user by name; nothing secret is written to the task, the registry
# or the disk, and auto-logon stays off. The token has no Windows network logon (no SMB/AD shares);
# HTTPS to Anthropic does not need one, and the CLI reads this user's own sign-in from this user's
# profile, which Task Scheduler loads for an S4U task. The task then runs in session 0 (no
# desktop), so the bridge no longer depends on an RDP session existing at all: it starts at boot,
# survives logoff, and the at-logon trigger becomes a harmless extra start (the mutex is per
# session, and every run of this one task is in session 0).
#   ONE TASK, ONE PRINCIPAL. -AtStartup swaps this same task's principal from Interactive to S4U and
#   adds a boot trigger; it never registers a second task, so there is still one scheduler entry and
#   one watchdog. Without the switch the task is registered exactly as before (Interactive, at logon).
#   NO DOUBLE BRIDGE DURING THE SWITCH. A watchdog already running in this user's RDP session holds
#   its own session's mutex, and a session-0 copy started now would not see it; both would restart
#   the server when it next exits. So when the heartbeat says a watchdog is alive (fresh within three
#   of its own promised intervals), the S4U task is registered but NOT started: it takes over at the
#   next boot, when no RDP copy exists. With no live heartbeat it is started at once.
#   PROOF. The watchdog's heartbeat carries session_id, boot_at and started_after_boot_s;
#   bridge_status.ps1 prints boot_start=PROVEN once a session-0 watchdog began within 15 min of a
#   boot, and boot_start=UNPROVEN until then (run ops\reboot_drill.ps1 or wait for the next reboot).
#   ROLLBACK. Re-run this installer without -AtStartup: the same task returns to Interactive.
#
# Idempotent; touches no other task. Read the result with ops\bridge\bridge_status.ps1.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File ops\bridge\install_bridge_watchdog.ps1 [-AtStartup]

[CmdletBinding()]
param(
    [string] $Checkout = "C:\opt\bridge\quant",
    [string] $Root = "C:\ProgramData\ClaudeBridge",
    [switch] $SkipCheckoutLock,
    [switch] $AtStartup,
    [ValidateSet("same-dir", "worktree")] [string] $SpawnMode = "same-dir"
)
$BinDir = Join-Path $Root "bin"
$LogDir = Join-Path $Root "logs"
# Highest, not a choice: the bin folder below is Administrators + SYSTEM only, so a limited token
# could not even read the script it runs.
$RunLevel = "Highest"
$ErrorActionPreference = 'Stop'

$TaskName = 'Claude-Bridge-Watchdog'
# THE CHECKOUT ARGUMENT IS CHECKED BEFORE ANYTHING IS LOCKED OR RE-OWNED (audit v1.4-v1.6): its
# parent folder is reset recursively, so a mistaken -Checkout would re-ACL whatever holds it (the
# live desk, C:\Users ...). An allow-list, not a deny-list: the checkout must be an existing git
# checkout, resolved by the file system (no \\?\ or UNC spelling survives Get-Item's FullName),
# directly inside <system drive>\opt\bridge, and nothing else in that folder may be a repository.
$bridgeDir = Join-Path $env:SystemDrive "opt\bridge"
try { $Checkout = (Get-Item -LiteralPath $Checkout -Force -ErrorAction Stop).FullName.TrimEnd('\') }
catch { throw "-Checkout $Checkout does not exist; not installing" }
if (-not (Test-Path -LiteralPath (Join-Path $Checkout ".git"))) { throw "-Checkout $Checkout is not a git checkout; not installing" }
$parent = Split-Path -Parent $Checkout
if ($parent -ine $bridgeDir) { throw "-Checkout $Checkout is not directly inside $bridgeDir; not installing" }
# NO JUNCTION ON THE WAY TO THE CHECKOUT OR INSIDE IT (audit v1.7): the parent is locked and reset
# recursively, so a junction there would carry an elevated re-ACL to wherever it points (the live
# desk). The repository tracks no symlinks, so any reparse point here was planted.
foreach ($p in @((Split-Path -Parent $bridgeDir), $bridgeDir, $Checkout)) {
    if ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "$p is a junction or symlink; not installing"
    }
}
foreach ($sib in @(Get-ChildItem -LiteralPath $parent -Directory -Force -ErrorAction SilentlyContinue)) {
    if ($sib.FullName -ine $Checkout -and (Test-Path -LiteralPath (Join-Path $sib.FullName ".git"))) {
        throw "$parent also holds the repository $($sib.FullName); locking it is not this installer's call"
    }
}
$src = Join-Path $PSScriptRoot 'bridge_watchdog.ps1'
if (-not (Test-Path $src)) { throw "bridge_watchdog.ps1 missing at $src" }
# THE FOLDERS THE ELEVATED TASK RUNS FROM AND WRITES TO ARE ADMIN-ONLY. A new folder under C:\
# inherits a DACL that normally lets Authenticated Users modify it, which would make bin a writable
# script run elevated and logs a forgeable heartbeat and, through a junction, an elevated write or
# delete anywhere. Inheritance is cut; only Administrators and SYSTEM keep any right (logs: Users
# may read). Files already inside lose any explicit entry (icacls /reset on the children), and the
# copy and its pin are deleted and written fresh, never written over a file someone pre-created.
# The pin protects against non-admins only: an administrator can rewrite the pin and the copy.
# THE CLI'S OWN `latest` DEBUG LINK IS THE ONE REPARSE POINT ALLOWED (2026-11-05, Desk health).
# `claude remote-control --debug-file <file>` drops a symbolic link named `latest` beside the file.
# The child walk refused it, so from the watchdog's first restart (10-28 13:46Z) every run exited 4
# and the bridge stayed down. Exactly one shape is exempt, identically in the watchdog, its status
# reader and the installer: a SymbolicLink (never a junction or mount point) named `latest` directly
# in the log folder, whose single target is a regular, non-reparse file directly in that same folder
# named rc_debug_YYYYMMDD_HHMMSS.log. Anything else, or anything that cannot be read, stays a refusal.
function Test-DebugLatestLink($c, [string] $logDir) {
    try {
        if ($c.Name -cne 'latest') { return $false }
        if ([string]$c.LinkType -cne 'SymbolicLink') { return $false }
        $ld = [IO.Path]::GetFullPath($logDir).TrimEnd([IO.Path]::DirectorySeparatorChar)
        if ([IO.Path]::GetFullPath($c.FullName) -ne (Join-Path $ld 'latest')) { return $false }
        $t = @($c.Target)
        if ($t.Count -ne 1 -or -not $t[0]) { return $false }
        $tp = [IO.Path]::GetFullPath([IO.Path]::Combine($ld, [string]$t[0]))
        if ((Split-Path -Parent $tp) -ne $ld) { return $false }
        if ((Split-Path -Leaf $tp) -cnotmatch '^rc_debug_\d{8}_\d{6}\.log$') { return $false }
        $f = Get-Item -LiteralPath $tp -Force -ErrorAction Stop
        if ($f.PSIsContainer) { return $false }
        if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { return $false }
        return $true
    } catch { return $false }
}
function Lock-Folder([string] $dir, [switch] $UsersRead, [switch] $KeepOwner) {
    if ((Test-Path -LiteralPath $dir) -and ((Get-Item -LiteralPath $dir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "$dir is a junction or symlink; not installing"
    }
    # every junction below is refused BEFORE any ACL or owner is set (audit v1.8 ordering note)
    if (Test-Path -LiteralPath $dir) {
        foreach ($c in @(Get-ChildItem -LiteralPath $dir -Force -Recurse)) {
            if (-not ($c.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
            if (Test-DebugLatestLink $c $LogDir) { continue }
            throw "$($c.FullName) is a junction or symlink; not installing"
        }
    }
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $grants = @("*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F")
    if ($UsersRead) { $grants += "*S-1-5-32-545:(OI)(CI)RX" }
    & icacls.exe $dir /inheritance:r /grant:r @grants | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls could not restrict $dir (exit $LASTEXITCODE)" }
    if (-not $KeepOwner) { & icacls.exe $dir /setowner "*S-1-5-32-544" /T /C | Out-Null }
    # ...and again once the folder is locked, right before the recursive reset: until the
    # /inheritance:r above, a non-admin could still plant one (audit v1.9 race)
    foreach ($c in @(Get-ChildItem -LiteralPath $dir -Force -Recurse)) {
        if (-not ($c.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
        if (Test-DebugLatestLink $c $LogDir) { continue }
        throw "$($c.FullName) is a junction or symlink; not installing"
    }
    if (@(Get-ChildItem -LiteralPath $dir -Force).Count -gt 0) {
        & icacls.exe (Join-Path $dir "*") /reset /T /C | Out-Null
    }
    $allowed = @('S-1-5-32-544', 'S-1-5-18')
    if ($UsersRead) { $allowed += 'S-1-5-32-545' }
    $writeMask = [int64][System.Security.AccessControl.FileSystemRights]"Write, Delete, DeleteSubdirectoriesAndFiles, ChangePermissions, TakeOwnership" -bor 0x50000000
    foreach ($path in @($dir) + @(Get-ChildItem -LiteralPath $dir -Force -Recurse | ForEach-Object { $_.FullName })) {
        foreach ($a in (Get-Acl -LiteralPath $path).Access | Where-Object { $_.AccessControlType -eq 'Allow' }) {
            $sid = $a.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
            if ($sid -notin $allowed) { throw "$path still grants $($a.IdentityReference); not installing" }
            if ($sid -eq 'S-1-5-32-545' -and ([int64]$a.FileSystemRights -band $writeMask) -ne 0) {
                throw "$path grants Users write; not installing"
            }
        }
    }
}
# A ROOT SOMEONE ELSE CREATED IS REFUSED, NOT TAKEN OVER (audit v1.3): access is checked when a
# handle opens, so a pre-creator holding an add-file or WRITE_DAC handle keeps it through any
# change of owner or ACL. An administrator deletes such a root (after reading what is in it) and
# re-runs this installer.
# A NEW ROOT IS CREATED WITH ITS LOCKED ACL IN ONE CALL (audit v1.4): created first and locked after,
# a user could create bin or logs inside it in between and keep that handle.
if (-not (Test-Path -LiteralPath $Root)) {
    $sec = New-Object System.Security.AccessControl.DirectorySecurity
    $sec.SetAccessRuleProtection($true, $false)
    $sec.SetOwner((New-Object System.Security.Principal.SecurityIdentifier 'S-1-5-32-544'))
    foreach ($ace in @(@('S-1-5-32-544', 'FullControl'), @('S-1-5-18', 'FullControl'), @('S-1-5-32-545', 'ReadAndExecute'))) {
        $sec.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier $ace[0]), $ace[1], 'ContainerInherit, ObjectInherit', 'None', 'Allow')))
    }
    $null = [System.IO.Directory]::CreateDirectory($Root, $sec)
}
foreach ($d in @($Root, $BinDir, $LogDir)) {
    if (-not (Test-Path -LiteralPath $d)) { continue }
    $dOwner = (New-Object System.Security.Principal.NTAccount((Get-Acl -LiteralPath $d).Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($dOwner -notin @('S-1-5-32-544', 'S-1-5-18')) {
        throw "$d already exists and is owned by $dOwner, not Administrators/SYSTEM; delete $Root as an administrator and re-run"
    }
}
Lock-Folder $Root -UsersRead
Lock-Folder $BinDir
Lock-Folder $LogDir -UsersRead
# The folder that holds the checkout is locked with it, so the checkout cannot be renamed away
# from under the sessions (C:\opt above it holds the live desk and is left alone).
if (-not $SkipCheckoutLock) { Lock-Folder (Split-Path -Parent $Checkout) -UsersRead -KeepOwner }
# GIT ACCEPTS ONLY A CHECKOUT ITS USER OWNS. This user is an administrator, so owning the folder
# gives nobody a right they lacked; the watchdog's checkout check already allows this owner.
$me = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
foreach ($d in @($Checkout, (Join-Path $Checkout ".git"))) {
    if (-not (Test-Path -LiteralPath $d)) { continue }
    & icacls.exe $d /setowner "*$me" /C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls could not make $me the owner of $d (exit $LASTEXITCODE)" }
    # OWNER RIGHTS, read only, on the folder itself (audit v1.5): the owner's implicit WRITE_DAC
    # and READ_CONTROL give way to this entry, so owning the folder grants nothing extra; git
    # checks only who the owner is.
    & icacls.exe $d /grant:r "*S-1-3-4:(RX)" /C | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "icacls could not limit OWNER RIGHTS on $d (exit $LASTEXITCODE)" }
}
$dst = Join-Path $BinDir 'bridge_watchdog.ps1'
$pinFile = Join-Path $BinDir 'watchdog.sha256'
Remove-Item -LiteralPath $dst, $pinFile -Force -ErrorAction SilentlyContinue
Copy-Item -Path $src -Destination $dst
$sha = (Get-FileHash $dst -Algorithm SHA256).Hash.ToLower()
Set-Content -Path $pinFile -Value $sha -Encoding ascii
"copied {0} -> {1} (sha256 {2}); {3} and {4} are Administrators + SYSTEM only ({4}: Users read)" -f $src, $dst, $sha.Substring(0, 12), $BinDir, $LogDir

$user = "{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument `
    ('-NoProfile -NonInteractive -WindowStyle Minimized -ExecutionPolicy Bypass -File "{0}" -Checkout "{1}" -LogDir "{2}" -SpawnMode {3}' -f $dst, $Checkout, $LogDir, $SpawnMode)

# AT LOGON, AND A DAILY TRIGGER REPEATING EVERY FIVE MINUTES FOR ONE DAY -- never a -Once trigger with
# a long duration: the desk measured one fold into P9D and expire (install_adopt_release_task.ps1).
$atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
$rearm = New-ScheduledTaskTrigger -Daily -At ((Get-Date).Date)
$rearm.Repetition = (New-ScheduledTaskTrigger -Once -At ((Get-Date).Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

# No time limit: the watchdog is meant to run for as long as the session lives. IgnoreNew so a
# re-arm never stacks a second copy; the mutex inside is the second lock.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

$triggers = @($atLogon, $rearm)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel $RunLevel
# PROBE BEFORE SWITCHING (2026-11-13). Whether the CLI can read this user's sign-in from an S4U
# token (no logon password, so nothing protected by the user's logon secret can be unlocked) is a
# fact of this box, not of this script, so it is MEASURED: a one-shot task with the same principal
# runs `claude auth status` once and writes its output to the admin-only log folder, and is then
# unregistered. Only "loggedIn": true switches the watchdog to S4U; anything else (false, no output
# in 90 s, unparseable) keeps it Interactive and says why, so -AtStartup can never leave the bridge
# signed out at boot. The probe changes nothing: `auth status` only reads.
function Test-S4USignIn {
    $claudeExe = $null
    foreach ($cand in @("$env:USERPROFILE\.local\bin\claude.exe", "$env:LOCALAPPDATA\Programs\claude\claude.exe")) {
        if (Test-Path -LiteralPath $cand) { $claudeExe = $cand; break }
    }
    if (-not $claudeExe) { return "claude.exe not found in this user's install paths" }
    $probeOut = Join-Path $LogDir 's4u_probe.txt'
    $probeTask = 'Claude-Bridge-S4U-Probe'
    Remove-Item -LiteralPath $probeOut -Force -ErrorAction SilentlyContinue
    # cmd's redirection captures the CLI's output; the task runs exactly `claude.exe auth status`
    $pa = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument ('/d /c ""{0}" auth status > "{1}" 2>&1"' -f $claudeExe, $probeOut)
    $pp = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel $RunLevel
    $ps = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
    try {
        Register-ScheduledTask -TaskName $probeTask -Action $pa -Principal $pp -Settings $ps -Force | Out-Null
        Start-ScheduledTask -TaskName $probeTask
        $deadline = (Get-Date).AddSeconds(90)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 3
            if ((Get-ScheduledTask -TaskName $probeTask).State -ne 'Running' -and (Test-Path -LiteralPath $probeOut)) { break }
        }
    } finally {
        Unregister-ScheduledTask -TaskName $probeTask -Confirm:$false -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path -LiteralPath $probeOut)) { return "the S4U probe wrote nothing within 90 s" }
    $txt = Get-Content -LiteralPath $probeOut -Raw
    # the status names the account; it is read here once and not left in a Users-readable folder
    Remove-Item -LiteralPath $probeOut -Force -ErrorAction SilentlyContinue
    try {
        $j = $txt | ConvertFrom-Json -ErrorAction Stop
        if ($j.loggedIn -eq $true) { return $null }
        return "claude auth status under S4U says loggedIn=$($j.loggedIn)"
    } catch {
        if ($txt.Length -gt 200) { $txt = $txt.Substring(0, 200) }
        return "claude auth status under S4U was not JSON: $txt"
    }
}
if ($AtStartup) {
    $s4uWhy = Test-S4USignIn
    if ($s4uWhy) {
        "AT_STARTUP_REFUSED: $s4uWhy -- keeping the task Interactive (at logon); nothing else changes"
        $AtStartup = $false
    } else { "S4U probe: signed in without a logon session; switching to boot start" }
}
if ($AtStartup) {
    # S4U: no password is passed, prompted for or stored (see the header). The boot trigger fires
    # before any logon; the 5-minute re-arm and the at-logon trigger still bring back a killed copy.
    $triggers = @((New-ScheduledTaskTrigger -AtStartup), $atLogon, $rearm)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel $RunLevel
}
# IS A WATCHDOG ALREADY ALIVE? Read before the task is replaced; decides whether to start it now.
$beat = Join-Path $LogDir 'bridge_watchdog.json'
$liveBefore = $false
try {
    $b0 = Get-Content -LiteralPath $beat -Raw -ErrorAction Stop | ConvertFrom-Json
    $every0 = 60
    if ($b0.beat_every_s -and [int]$b0.beat_every_s -gt 60) { $every0 = [int]$b0.beat_every_s }
    $age0 = ((Get-Date).ToUniversalTime() - ([datetime]$b0.at).ToUniversalTime()).TotalSeconds
    $liveBefore = ($age0 -le 3 * $every0) -and ($b0.state -eq 'RUNNING')
} catch { }

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers `
    -Principal $principal -Settings $settings `
    -Description "Keep the box bridge (claude remote-control in $Checkout) running; restart it when it exits." | Out-Null

$mode = 'Interactive (at logon)'
if ($AtStartup) { $mode = 'S4U (at boot, no stored password)' }
if ($AtStartup -and $liveBefore) {
    "registered {0} as {1}; a watchdog is alive in an interactive session, so the S4U task is NOT started now (no second bridge); it takes over at the next boot" -f $TaskName, $mode
} else {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 8
}
$i = Get-ScheduledTaskInfo -TaskName $TaskName
"installed {0} ({5}): state={1} last_run={2} last_result={3} logon_type={4}" -f $TaskName, (Get-ScheduledTask -TaskName $TaskName).State, $i.LastRunTime, $i.LastTaskResult, (Get-ScheduledTask -TaskName $TaskName).Principal.LogonType, $mode
if (Test-Path $beat) { "heartbeat: " + ((Get-Content $beat -Raw | ConvertFrom-Json) | ConvertTo-Json -Compress) }
