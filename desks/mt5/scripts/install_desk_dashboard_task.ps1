# The 24/7 desk dashboard: a listener that starts at boot and restarts on failure.
#
# WHY A SECOND LISTENER. `install_local_dashboard.ps1` registers MT5-LocalDashboard bound to
# 127.0.0.1, which is right for a page read over RDP and useless from a phone. This task runs the
# repo's own `scripts/serve_dashboard.py` -- stdlib http.server, threaded, read-only over `web/`
# -- so the page is reachable from the principal's other devices without a tunnel, a DNS record
# or a certificate to expire.
#
# NO TOKEN, AND AN OPEN PORT (principal, 2026-11-18, after being warned that this publishes the
# live equity, P&L and open positions to anyone who finds the address). He asked for it twice. What
# makes it tolerable, and what this script still enforces:
#   read-only     the server answers GET and HEAD only (no POST route exists), serves the 7 files of
#                 web/ and nothing else, and a request runs nothing -- the page's data is rebuilt on
#                 the box's own clock by MT5-DeskState. No key, login or credential is in any page.
#   the address   the box's own fixed address on this port: permanent, nothing to mint or renew.
#   the rule      one inbound firewall rule for this one port; -AllowFrom narrows it again.
# The old --require-token gate and the LocalSubnet scope are gone by design, not by accident.

param(
  [int]$Port = 8080,
  [string]$TaskName = 'MT5-DeskDashboard',
  # Empty (the default) opens the port to every address. To narrow it again, name them:
  #     .\install_desk_dashboard_task.ps1 -AllowFrom '203.0.113.4','198.51.100.0/24'
  [string[]]$AllowFrom = @()
)

$repo = 'C:\opt\quant'
$py = 'C:\Program Files\Python314\python.exe'
$script = Join-Path $repo 'scripts\serve_dashboard.py'
$page = Join-Path $repo 'web\dashboard.html'

if (-not (Test-Path $py))     { Write-Output "REFUSING: python not found at $py"; exit 1 }
if (-not (Test-Path $script)) { Write-Output "REFUSING: $script does not exist"; exit 1 }
if (-not (Test-Path $page))   { Write-Output "REFUSING: $page does not exist"; exit 1 }

$argline = "`"$script`" --port $Port --host 0.0.0.0 --no-auth"

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

# ONE INBOUND RULE FOR THIS PORT. Every address unless -AllowFrom narrows it.
$remotes = if ($AllowFrom.Count -gt 0) { @('LocalSubnet') + $AllowFrom } else { @('Any') }
try {
  Remove-NetFirewallRule -DisplayName "MT5 Desk Dashboard $Port" -ErrorAction SilentlyContinue
  New-NetFirewallRule -DisplayName "MT5 Desk Dashboard $Port" -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $Port -RemoteAddress $remotes -Profile Any | Out-Null
  Write-Output ("firewall: inbound TCP $Port allowed from " + ($remotes -join ', ') + " only")
} catch {
  Write-Output ("firewall: UNMEASURED -- " + $_.Exception.Message)
}

# RETIRE THE RANDOM QUICK TUNNEL (principal 2026-11-18): the fixed address replaces it. MT5-DeskTunnel ran
# scripts\run_tunnel.py, which is deleted; its cloudflared children (one is an orphan) are stopped here.
try {
  Stop-ScheduledTask -TaskName 'MT5-DeskTunnel' -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName 'MT5-DeskTunnel' -Confirm:$false -ErrorAction SilentlyContinue
  Get-Process -Name cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  Write-Output 'tunnel: MT5-DeskTunnel unregistered, cloudflared stopped'
} catch {
  Write-Output ("tunnel: UNMEASURED -- " + $_.Exception.Message)
}

Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 4
$state = (Get-ScheduledTask -TaskName $TaskName).State
Write-Output "${TaskName}: $state"

# The proof it is up: loopback must answer 200 for the page. A 401 would mean an old token-gated
# server is still the one running.
try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/dashboard.html" -UseBasicParsing -TimeoutSec 10
  if ($r.StatusCode -eq 200) { Write-Output "dashboard.html -> HTTP 200 (listener up, no token)" }
  else { Write-Output ("dashboard.html -> HTTP " + $r.StatusCode + " (unexpected)") }
} catch {
  Write-Output ("SERVE CHECK FAILED: " + $_.Exception.Message)
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' } |
       Select-Object -First 1 -ExpandProperty IPAddress)
Write-Output ""
Write-Output "ON THIS BOX      : http://127.0.0.1:$Port/dashboard.html"
Write-Output "PERMANENT ADDRESS: http://${ip}:$Port/dashboard.html"
