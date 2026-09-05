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
# THIS box. Serving it on loopback removes the entire chain: no tunnel, no DNS, no certificate, no
# token, nothing to expire and nothing to re-hand-over after a restart.
#
# BOUND TO 127.0.0.1 DELIBERATELY. This machine holds live broker credentials, and the page shows
# equity, positions and strategies. Loopback means the listener is not reachable from the network
# at all -- not a firewall rule that can be relaxed by accident, an interface that was never
# offered. Anyone who can read this page can already read the disk it is served from.
#
# The tunnel keeps running for phone access; this is the copy that always works.

$port = 8899
$web = 'C:\opt\quant\web'
$py = 'C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe'

if (-not (Test-Path $web)) { Write-Output "REFUSING: $web does not exist"; exit 1 }
if (-not (Test-Path $py))  { Write-Output "REFUSING: python not found at $py"; exit 1 }

# --bind 127.0.0.1 is the security property; -d serves the web directory without a chdir that
# would leak the rest of the disk if the working directory ever changed.
$argline = "-m http.server $port --bind 127.0.0.1 -d `"$web`""

$action = New-ScheduledTaskAction -Execute $py -Argument $argline -WorkingDirectory $web
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
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/desk.html" -UseBasicParsing -TimeoutSec 10
  Write-Output ("desk.html -> HTTP " + $r.StatusCode + " (" + $r.RawContentLength + " bytes)")
  $s = Invoke-WebRequest -Uri "http://127.0.0.1:$port/desk_state.json" -UseBasicParsing -TimeoutSec 10
  Write-Output ("desk_state.json -> HTTP " + $s.StatusCode + " (" + $s.RawContentLength + " bytes)")
  Write-Output ""
  Write-Output "OPEN THIS ON THIS MACHINE:  http://localhost:$port/desk.html"
} catch {
  Write-Output ("SERVE CHECK FAILED: " + $_.Exception.Message)
  exit 1
}
