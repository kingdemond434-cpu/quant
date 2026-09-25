# Serve the desk dashboard from the trading box itself, on loopback, forever.
#
# WHY THIS EXISTS. The dashboard was reachable only through a Cloudflare tunnel terminating on the
# VPS, which put four things in the path between the principal and a page whose data is BUILT ON
# THIS MACHINE: a quick tunnel that minted a new hostname on every restart, a QUIC transport that
# dropped every connection for hours while systemd reported the unit healthy, a DNS record, and a
# browser cache. Each was fixed in turn and the page still would not open, which is the point --
# every one of those was a dependency the page never needed.
#
# `desk_state.json` is written HERE by MT5-DeskState, and the principal reads it while logged into
# THIS box. Serving it on loopback removes the entire chain: no tunnel, no DNS, no certificate,
# nothing to expire and nothing to re-hand-over after a restart (the token below is a cookie).
#
# BOUND TO 127.0.0.1 DELIBERATELY. This machine holds live broker credentials, and the page shows
# equity, positions and strategies. Loopback means the listener is not reachable from the network
# at all -- not a firewall rule that can be relaxed by accident, an interface that was never
# offered. But loopback is exactly where a tunnel delivers its traffic, so binding is NOT the
# gate -- the token is (see below).
#
# TOKEN-GATED SINCE 2026-09-25. This used to run a bare `python -m http.server`, and
# desks/mt5/scripts/dashboard_tunnel.py published that unauthenticated listener to the internet
# through a cloudflared quick tunnel -- loopback binding protects nothing once a tunnel forwards
# into it. The tunnel is retired (it now refuses to run) and this task runs the desk's own
# scripts/serve_dashboard.py, which requires the token on EVERY request, loopback included.
# Open the page once as http://localhost:8899/desk.html?k=<key> (key: data\secrets\dashboard_token.txt,
# read on the box, never printed); the link sets a cookie so later visits need nothing.

$port = 8899
$root = 'C:\opt\quant'
$web = Join-Path $root 'web'
$script = Join-Path $root 'scripts\serve_dashboard.py'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe'

if (-not (Test-Path $web))    { Write-Output "REFUSING: $web does not exist"; exit 1 }
if (-not (Test-Path $script)) { Write-Output "REFUSING: $script does not exist"; exit 1 }
if (-not (Test-Path $py))     { Write-Output "REFUSING: python not found at $py"; exit 1 }

# --host 127.0.0.1 keeps it off the network; the token (on by default) is what protects it if
# anything ever forwards into this port.
$argline = "`"$script`" --port $port --host 127.0.0.1 --require-token"

$action = New-ScheduledTaskAction -Execute $py -Argument $argline -WorkingDirectory $root
# AtStartup so it survives the reboots this desk actually takes, and a restart-on-failure so a
# crashed listener comes back without anyone noticing it went.
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
              -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName 'MT5-LocalDashboard' -Action $action -Trigger $trigger `
  -Settings $settings -User 'Administrator' -RunLevel Highest -Force | Out-Null

Start-ScheduledTask -TaskName 'MT5-LocalDashboard'
Start-Sleep -Seconds 3

$state = (Get-ScheduledTask -TaskName 'MT5-LocalDashboard').State
Write-Output "MT5-LocalDashboard: $state"
# The proof it is up AND gated: an unauthenticated request must get the 401 login page.
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/desk.html" -UseBasicParsing -TimeoutSec 10
  Write-Output ("desk.html -> HTTP " + $r.StatusCode + " (TOKEN GATE OFF -- investigate)")
  exit 1
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 401) {
    Write-Output "desk.html -> HTTP 401 login page (token gate ON, listener up)"
    Write-Output ""
    Write-Output "OPEN THIS ON THIS MACHINE:  http://localhost:$port/desk.html?k=<key from data\secrets\dashboard_token.txt>"
  } else {
    Write-Output ("SERVE CHECK FAILED: " + $_.Exception.Message)
    exit 1
  }
}
