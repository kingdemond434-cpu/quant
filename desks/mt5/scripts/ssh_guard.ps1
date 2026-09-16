# SSH GUARD -- fail2ban for the Windows box that trades (2026-09-16).
#
# WHY. One address made 1,351 failed logins in a single OpenSSH/Operational log window, with four
# others behind it. Password authentication is off, so none of them could get in -- but each
# attempt occupied a pre-authentication slot for the grace time, and at the default
# `MaxStartups 10` with `LoginGraceTime 120` the pool was full often enough that one legitimate
# handshake in three was refused at key exchange ("kex_exchange_identification: Software caused
# connection abort"). The sshd limits (MaxStartups 100:30:300, PerSourceMaxStartups 5,
# LoginGraceTime 20) stop any one address filling the pool; this script stops a repeat offender
# from reaching sshd at all.
#
# WHAT IT DOES, every 5 minutes as MT5-SshGuard (SYSTEM):
#   1. reads the OpenSSH/Operational log for the last $windowMin minutes;
#   2. counts failures per source address (invalid user, failed password/publickey, pre-auth
#      disconnects, no identification string);
#   3. an address with >= $threshold failures gets an inbound BLOCK rule on TCP 22 named
#      SSHGuard-<ip> (port 22 only: a mistaken ban never touches RDP or the terminal);
#   4. bans older than $banDays are lifted; the allow-list is never banned;
#   5. the verdict lands in data\ssh_guard.json so the desk-state builder can show it.
#
# ADDING A SOURCE THAT MAY NEVER BE BANNED: put its address in $allow below. Lifting a ban by
# hand: Remove-NetFirewallRule -DisplayName 'SSHGuard-<ip>'.

$ErrorActionPreference = 'SilentlyContinue'
$base = 'C:\opt\quant\desks\mt5'
$stateFile = Join-Path $base 'data\ssh_guard.json'
$windowMin = 15
$threshold = 3
$banDays = 7
# The build box (VMI3500897), the Hetzner VPS (dash.quanttt.xyz) and loopback.
$allow = @('169.58.159.142', '95.216.191.70', '127.0.0.1')

$since = (Get-Date).AddMinutes(-$windowMin)
$events = @(Get-WinEvent -LogName 'OpenSSH/Operational' -MaxEvents 6000 -ErrorAction SilentlyContinue |
            Where-Object { $_.TimeCreated -gt $since })
$bad = @{}
$pattern = 'Invalid user|Failed (password|publickey|none)|\[preauth\]|Did not receive identification|Bad protocol version|Connection reset by|Unable to negotiate'
foreach ($e in $events) {
  $m = $e.Message
  if ($m -match 'from (\d+\.\d+\.\d+\.\d+)' -and $m -match $pattern) {
    $ip = $Matches[1]
    if ($m -match 'from (\d+\.\d+\.\d+\.\d+)') { $ip = $Matches[1] }
    if (-not $bad.ContainsKey($ip)) { $bad[$ip] = 0 }
    $bad[$ip] = $bad[$ip] + 1
  }
}

$existing = @(Get-NetFirewallRule -DisplayName 'SSHGuard-*' -ErrorAction SilentlyContinue)
$have = @{}
foreach ($r in $existing) { $have[$r.DisplayName] = $r }
$added = @(); $lifted = @(); $skipped = @()
foreach ($ip in $bad.Keys) {
  if ($allow -contains $ip) { $skipped += $ip; continue }
  if ($bad[$ip] -lt $threshold) { continue }
  $name = "SSHGuard-$ip"
  if ($have.ContainsKey($name)) { continue }
  $desc = 'banned ' + (Get-Date).ToString('s') + ' after ' + $bad[$ip] + ' failures in ' + $windowMin + ' min'
  New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Block -Protocol TCP -LocalPort 22 `
    -RemoteAddress $ip -Profile Any -Enabled True -Description $desc | Out-Null
  if ($?) { $added += $ip }
}
foreach ($r in $existing) {
  if ($r.Description -match 'banned (\S+) after') {
    $when = [datetime]::Parse($Matches[1])
    if (((Get-Date) - $when) -gt (New-TimeSpan -Days $banDays)) {
      Remove-NetFirewallRule -DisplayName $r.DisplayName | Out-Null
      $lifted += ($r.DisplayName -replace '^SSHGuard-', '')
    }
  }
}
$active = @(Get-NetFirewallRule -DisplayName 'SSHGuard-*' -ErrorAction SilentlyContinue | ForEach-Object { $_.DisplayName -replace '^SSHGuard-', '' })
$top = @($bad.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 8 | ForEach-Object { @{ ip = $_.Key; failures = $_.Value } })
$doc = @{
  at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  window_min = $windowMin; threshold = $threshold; ban_days = $banDays
  events_read = $events.Count
  offenders_in_window = $bad.Count
  top_offenders = $top
  banned_now = $added; lifted_now = $lifted; allow_listed_seen = $skipped
  active_bans = $active.Count
  active = $active
  why = 'pre-auth slots were exhausted by brute-force bots; sshd per-source limits plus this ban keep the pool free for the desk'
}
$doc | ConvertTo-Json -Depth 4 | Set-Content -Path $stateFile -Encoding UTF8
Write-Output ("ssh guard: {0} event(s), {1} offender(s), banned now {2}, lifted {3}, active bans {4}" -f $events.Count, $bad.Count, $added.Count, $lifted.Count, $active.Count)
