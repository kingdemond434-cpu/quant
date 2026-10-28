# AFTER A REBOOT, BRING THE DESK BACK WITHOUT ZUCK (2026-10-28).
#
# zuck: "I wish we could make it so even these become automated not needing me". Every reboot
# used to wait for zuck to RDP in, because the MT5 terminals are GUI processes and the MetaTrader5
# Python API reaches a terminal only from the SAME interactive desktop session (measured: from
# Session 0 / S4U / SYSTEM it fails -10004 "No IPC connection" while the task looks scheduled).
# So "run whether the user is logged on or not" cannot work for this desk; a logged-on desktop is
# the requirement. Windows AUTO-LOGON supplies it (Sysinternals Autologon keeps the password as an
# LSA secret, never in the registry in plain text); every AtLogOn task (gateway, FTMO follower,
# bridge watchdog, terminal boot) then starts as it does after zuck's RDP logon today.
#
# This script is what the Quant-BootSession task runs. Two modes:
#
#   -Mode Record   (every 10 minutes) writes which MT5 terminals run in this desktop session, so a
#                  reboot brings back exactly what was running -- nothing more. Fusion is left out:
#                  ops\ensure_terminal.ps1 (MT5-TerminalBoot) owns it, and two starters would race
#                  into two terminals on one data directory. Nothing is recorded in the first 15
#                  minutes after boot, so a half-started desk never overwrites the list.
#   -Mode Logon    (at this user's logon) starts every recorded terminal that runs in NO session
#                  (one in another session may own live state: it is logged and left alone, the
#                  caution of ensure_terminal.ps1), then LOCKS the console when this logon is the
#                  console session (the auto-logon one), so the provider's VNC console never shows
#                  an unlocked desktop. A locked session keeps every process and the MT5 IPC.
#
# It starts terminals and locks the screen; it never kills a process, never writes the registry,
# never reads or stores a password.

[CmdletBinding()]
param(
    [ValidateSet("Logon", "Record")] [string] $Mode = "Record",
    [string] $Root = "C:\ProgramData\QuantBox",
    [string] $Fusion = "C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe",
    [switch] $NoLock
)
$ErrorActionPreference = 'Stop'
$LogDir = Join-Path $Root "logs"
$list = Join-Path $LogDir "terminals.json"
$log = Join-Path $LogDir "boot_session.log"
$session = (Get-Process -Id $PID).SessionId
function Say([string] $line) {
    Add-Content -LiteralPath $log -Value ("{0} [{1} s{2}] {3}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'), $Mode, $session, $line)
}
if ($session -eq 0) { Say "in Session 0: no desktop here, nothing to do"; exit 2 }

# Get-Process, never CIM (CIM has hung on this box). A process whose Path cannot be read is not
# counted as ours.
function Get-Terminals {
    @(Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue | Where-Object { $_.Path })
}

if ($Mode -eq "Record") {
    if ([Environment]::TickCount64 -lt 15 * 60 * 1000) { exit 0 }
    $paths = @(Get-Terminals | Where-Object { $_.SessionId -eq $session -and $_.Path -ine $Fusion } |
        ForEach-Object { $_.Path } | Sort-Object -Unique)
    $doc = [ordered]@{ at = (Get-Date).ToUniversalTime().ToString('o'); session = $session; terminals = $paths }
    $tmp = "$list.tmp"
    $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $list -Force
    exit 0
}

# -Mode Logon. The network and the AtLogOn tasks come up together; give the terminals' servers a
# moment before they try to connect.
Start-Sleep -Seconds 30
$want = @()
if (Test-Path -LiteralPath $list) {
    try { $want = @((Get-Content -LiteralPath $list -Raw | ConvertFrom-Json).terminals) }
    catch { Say "terminals.json unreadable: $($_.Exception.Message); starting none" }
} else { Say "no terminals.json yet (first boot after install); starting none" }
$rc = 0
foreach ($exe in $want) {
    if (-not $exe -or $exe -ieq $Fusion) { continue }
    $running = @(Get-Terminals | Where-Object { $_.Path -ieq $exe })
    if ($running.Count -gt 0) {
        Say ("{0} already runs in session(s) {1}; not starting another" -f $exe, (($running | ForEach-Object { $_.SessionId }) -join ','))
        continue
    }
    if (-not (Test-Path -LiteralPath $exe)) { Say "$exe missing; not started"; $rc = 2; continue }
    Start-Process -FilePath $exe
    Start-Sleep -Seconds 8
    $n = @(Get-Terminals | Where-Object { $_.Path -ieq $exe -and $_.SessionId -eq $session }).Count
    if ($n -eq 1) { Say "started $exe" } else { Say "started $exe but see $n of it in this session"; $rc = 2 }
}

if (-not $NoLock) {
    Add-Type -Namespace QuantBox -Name Win -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint WTSGetActiveConsoleSessionId();
[DllImport("user32.dll")] public static extern bool LockWorkStation();
'@
    if ([QuantBox.Win]::WTSGetActiveConsoleSessionId() -eq [uint32]$session) {
        if ([QuantBox.Win]::LockWorkStation()) { Say "console session locked" } else { Say "console lock FAILED"; $rc = 2 }
    } else { Say "not the console session (an RDP logon): not locked" }
}
exit $rc
