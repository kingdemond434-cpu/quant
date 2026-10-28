# READ THE BOX BRIDGE WATCHDOG'S HEARTBEAT AND SAY WHETHER THE BRIDGE IS ALIVE (2026-10-28). Read-only.
#
# The reader Desk health and the hourly pass run over the box bridge (`powershell -File
# ops\bridge\bridge_status.ps1`). One line, then exit 0 when LIVE and 1 otherwise:
#
#   LIVE        heartbeat younger than 180 s (the watchdog refreshes it every 60 s), state RUNNING,
#               the server pid alive, and the watchdog's own sha256 equal to the installer's pin
#   STALE       heartbeat older than 180 s: the watchdog itself is hung or dead (the 5-minute
#               re-arm should replace a dead one; a hung one holds its mutex and needs a person)
#   QUIET       RUNNING, but the server's debug file silent for over 30 min: likely parked at a
#               prompt or wedged; the watchdog does not kill it, a person or Desk health decides
#   <state>     anything else the watchdog wrote: NEEDS_LOGIN, TAMPERED, NO_CLAUDE, RESTARTING, ...
#   ABSENT      no heartbeat at all: the watchdog is not installed or never ran
param([string] $LogDir = "C:\opt\bridge\logs", [string] $BinDir = "C:\opt\bridge\bin")

$beat = Join-Path $LogDir "bridge_watchdog.json"
if (-not (Test-Path $beat)) { "ABSENT: no $beat"; exit 1 }
try { $b = Get-Content $beat -Raw | ConvertFrom-Json } catch { "ABSENT: $beat unreadable"; exit 1 }
$age = [int]((Get-Date).ToUniversalTime() - ([datetime]$b.at).ToUniversalTime()).TotalSeconds
$pin = ""
try { $pin = (Get-Content (Join-Path $BinDir "watchdog.sha256") -Raw -ErrorAction Stop).Trim().ToLower() } catch { }
$alive = $false
if ($b.server_pid) { $alive = [bool](Get-Process -Id ([int]$b.server_pid) -ErrorAction SilentlyContinue) }
$detail = "state=$($b.state) age_s=$age server_pid=$($b.server_pid) alive=$alive restarts=$($b.restarts) debug_quiet_s=$($b.debug_quiet_s) last_exit=$($b.last_exit_code)"
if ($age -gt 180) { "STALE: $detail"; exit 1 }
if ($pin -and $b.watchdog_sha256 -ne $pin) { "TAMPERED: running sha $($b.watchdog_sha256) vs pin $pin; $detail"; exit 1 }
if ($b.state -ne "RUNNING") { "$($b.state): $detail"; exit 1 }
if (-not $alive) { "DEAD_SERVER: $detail"; exit 1 }
if ($b.debug_quiet_s -and [int]$b.debug_quiet_s -gt 1800) { "QUIET: $detail"; exit 1 }
"LIVE: $detail"
exit 0
