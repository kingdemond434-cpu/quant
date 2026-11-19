# The 24/7 desk dashboard: a listener that starts at boot and restarts on failure.
#
# WHY A SECOND LISTENER. `install_local_dashboard.ps1` registers MT5-LocalDashboard bound to
# 127.0.0.1, which is right for a page read over RDP and useless from a phone. This task runs the
# repo's own `scripts/serve_dashboard.py` -- stdlib http.server, threaded, read-only over `web/`
# -- so the page is reachable from the principal's other devices without a tunnel, a DNS record
# or a certificate to expire.
#
# TWO CONTROLS, BOTH ON BY DEFAULT, because this box holds live broker credentials:
#   --require-token   every request off the box must carry the key (header, ?k=..., or the cookie
#                     the first link sets). The loopback exemption is DROPPED deliberately: a
#                     tunnel or proxy would otherwise arrive as 127.0.0.1 and bypass the gate.
#                     The key lives in data/secrets/dashboard_token.txt, 0600, and is never
#                     printed by this script or any other (CLAUDE.md: data/secrets/** never
#                     leaves the box).
#   firewall          the inbound rule is scoped to LocalSubnet, so the port is not offered to
#                     the public internet at all. "Not exposed" is an interface that was never
#                     opened, not a policy nobody enforces.
#
# The page itself is READ-ONLY: it fetches one JSON document and renders it. It has no form, no
# POST route and no parameter that reaches the desk, so nothing served here can change what is
# traded.

param(
  [int]$Port = 8080,
  [string]$TaskName = 'MT5-DeskDashboard',
  # THIS BOX HAS NO PRIVATE LAN: its only IPv4 address is public, so "LocalSubnet" here means
  # essentially nothing else can reach it -- which is the safe default and also means a phone on
  # a home network cannot. Enrol the devices you actually use by their address, explicitly:
  #     .\install_desk_dashboard_task.ps1 -AllowFrom '203.0.113.4','198.51.100.0/24'
  # The token is still required from every one of them. Opening the port to 'Any' is refused.
  [string[]]$AllowFrom = @()
)

$repo = 'C:\opt\quant'
$py = 'C:\Program Files\Python314\python.exe'
$script = Join-Path $repo 'scripts\serve_dashboard.py'
$page = Join-Path $repo 'web\dashboard.html'

if (-not (Test-Path $py))     { Write-Output "REFUSING: python not found at $py"; exit 1 }
if (-not (Test-Path $script)) { Write-Output "REFUSING: $script does not exist"; exit 1 }
if (-not (Test-Path $page))   { Write-Output "REFUSING: $page does not exist"; exit 1 }

$argline = "`"$script`" --port $Port --host 0.0.0.0 --require-token"

$action = New-ScheduledTaskAction -Execute $py -Argument $argline -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtStartup
# RestartCount/RestartInterval are what make this PERMANENT rather than a process someone
# started: a crashed listener is back within a minute, and a rebooted box brings it up itself.
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
              -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
              -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

# LOCAL NETWORK ONLY. Scoped to LocalSubnet so the listener is not reachable from the internet
# even though it binds 0.0.0.0; the token is the second control, not the only one.
$remotes = @('LocalSubnet') + $AllowFrom
if ($remotes -contains 'Any' -or $remotes -contains '*') {
  Write-Output "REFUSING: -AllowFrom Any would publish live equity to the internet"; exit 1
}
try {
  Remove-NetFirewallRule -DisplayName "MT5 Desk Dashboard $Port" -ErrorAction SilentlyContinue
  New-NetFirewallRule -DisplayName "MT5 Desk Dashboard $Port" -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $Port -RemoteAddress $remotes -Profile Any | Out-Null
  Write-Output ("firewall: inbound TCP $Port allowed from " + ($remotes -join ', ') + " only")
} catch {
  Write-Output ("firewall: UNMEASURED -- " + $_.Exception.Message)
}

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 4
$state = (Get-ScheduledTask -TaskName $TaskName).State
Write-Output "${TaskName}: $state"

# The proof it is up AND gated: loopback must answer 401 with --require-token. A 200 here would
# mean the token gate is off, which is a defect on a box with a public address.
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/dashboard.html" -UseBasicParsing -TimeoutSec 10
  Write-Output ("dashboard.html -> HTTP " + $r.StatusCode + " (TOKEN GATE OFF -- investigate)")
} catch {
  $code = $null
  if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
  if ($code -eq 401) { Write-Output "dashboard.html -> HTTP 401 login page (token gate ON, listener up)" }
  else { Write-Output ("SERVE CHECK FAILED: " + $_.Exception.Message) }
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' } |
       Select-Object -First 1 -ExpandProperty IPAddress)
Write-Output ""
Write-Output "ON THIS BOX      : http://127.0.0.1:$Port/dashboard.html"
Write-Output "ON THE NETWORK   : http://${ip}:$Port/dashboard.html?k=<key>"
Write-Output "KEY              : read it on the box, once, from data\secrets\dashboard_token.txt"
Write-Output "                   (never printed here; the first link sets a year-long cookie)"
