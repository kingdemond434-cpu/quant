# READ THE BOX BRIDGE WATCHDOG'S HEARTBEAT AND SAY WHETHER THE BRIDGE IS ALIVE (2026-10-28). Read-only.
#
# Run by hand or by Desk health on the box (`powershell -File ops\bridge\bridge_status.ps1`, from an
# elevated shell so the admin-only pin can be read). No scheduled caller is wired yet: a bridge that
# is down cannot carry its own status to a thread, so the reader that matters is a person or a Desk
# health session reaching the box another way. One line, then exit 0 when LIVE and 1 otherwise:
#
#   UNSAFE      the bin or log folder grants write to anyone but Administrators/SYSTEM, a folder
#               above them can be renamed or re-permissioned by anyone else, or a junction or symlink
#               sits in or above them: nothing there can be trusted, and the watchdog refuses to run
#               (its task's last result reads 4, printed here too)
#   TAMPERED    the copy in bin no longer hashes to the installer's pin (hashed HERE, never taken
#               from the heartbeat's own word)
#   STALE       no heartbeat within three of the watchdog's own promised intervals (`beat_every_s`:
#               60 s while it lives, 300 s for a state written just before exit) -- hung or dead
#   <state>     anything else the watchdog wrote: NEEDS_LOGIN, RESTARTING, START_FAILED, NO_CLAUDE,
#               ... with next_in_s when it is waiting on purpose
#   DEAD_SERVER RUNNING, but the server pid is gone
#   UNMEASURED  RUNNING, but no debug file of the watchdog's to measure the server by
#   QUIET       RUNNING, but the server's debug file silent for over 30 min: parked or wedged
#   DEGRADED    RUNNING, but 3 or more debug-file lines in the last 10 min name failed or exited
#               sessions (a server that accepts a session and loses it at once is alive to a process
#               check and useless to a thread)
#   LIVE_CHECKOUT_AT_RISK   LIVE, but a non-admin could write the checkout the elevated sessions
#               run in (or its .claude / git hooks) or rename a folder above it; exit 2 -- the
#               bridge works, but automation must not read it as healthy -- and the line says
#               what to lock
#   ABSENT      no heartbeat at all: the watchdog is not installed or never ran
param([string] $LogDir = "C:\ProgramData\ClaudeBridge\logs", [string] $BinDir = "C:\ProgramData\ClaudeBridge\bin",
      [string] $TaskName = "Claude-Bridge-Watchdog")

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
$taskResult = "unread"
try { $taskResult = [string](Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop).LastTaskResult } catch { }
foreach ($d in @($BinDir, $LogDir)) {
    $why = Get-UnsafeReason $d
    if ($why) { "UNSAFE: $why (task last result $taskResult)"; exit 1 }
}
$pin = ""
try { $pin = (Get-Content (Join-Path $BinDir "watchdog.sha256") -Raw -ErrorAction Stop).Trim().ToLower() } catch { }
$copy = Join-Path $BinDir "bridge_watchdog.ps1"
$sha = ""
try { $sha = (Get-FileHash -LiteralPath $copy -Algorithm SHA256 -ErrorAction Stop).Hash.ToLower() } catch { }
if (-not $pin -or -not $sha) { "TAMPERED: pin or copy unreadable (run elevated): pin='$pin' copy='$sha'"; exit 1 }
if ($sha -ne $pin) { "TAMPERED: $copy hashes to $sha, pin is $pin"; exit 1 }

$beat = Join-Path $LogDir "bridge_watchdog.json"
if (-not (Test-Path $beat)) { "ABSENT: no $beat"; exit 1 }
try { $b = Get-Content $beat -Raw | ConvertFrom-Json } catch { "ABSENT: $beat unreadable"; exit 1 }
$age = [int]((Get-Date).ToUniversalTime() - ([datetime]$b.at).ToUniversalTime()).TotalSeconds
$every = 60
if ($b.beat_every_s) { $every = [Math]::Max(60, [int]$b.beat_every_s) }
$alive = $false
if ($b.server_pid) { $alive = [bool](Get-Process -Id ([int]$b.server_pid) -ErrorAction SilentlyContinue) }
$detail = "state=$($b.state) age_s=$age every_s=$every server_pid=$($b.server_pid) alive=$alive restarts=$($b.restarts) debug_quiet_s=$($b.debug_quiet_s) session_errors_10m=$($b.session_errors_10m) task_result=$taskResult last_exit=$($b.last_exit_code) next_in_s=$($b.next_in_s)"
if ($age -gt 3 * $every) { "STALE: $detail"; exit 1 }
if ($b.state -ne "RUNNING") { "$($b.state): $detail needs=$($b.needs)"; exit 1 }
if (-not $alive) { "DEAD_SERVER: $detail"; exit 1 }
if ($null -eq $b.debug_quiet_s) { "UNMEASURED: $detail"; exit 1 }
if ([int]$b.debug_quiet_s -gt 1800) { "QUIET: $detail"; exit 1 }
if ($b.session_errors_10m -and [int]$b.session_errors_10m -ge 3) { "DEGRADED: $detail last=$($b.last_session_error)"; exit 1 }
if ($b.checkout_risk) { "LIVE_CHECKOUT_AT_RISK: $($b.checkout_risk); $detail"; exit 2 }
"LIVE: $detail"
exit 0
