# PRIVATE NETWORK for the Windows box that trades (2026-09-30): SSH and RDP reachable only from
# the tailnet and the desk's own named machines, never from the whole internet.
#
# WHY. The infra survey found TCP 22 and 3389 open to any address. ssh_guard.ps1 bans repeat
# offenders after they have already reached sshd, and password auth is off, so nothing has got
# in -- but RDP has no such guard, and every exposed port is a pre-auth attack surface on the one
# machine holding the live terminal. The elite-solo baseline is a private overlay (WireGuard /
# Tailscale) with the management ports closed to everything else.
#
# THREE MODES, AND ONLY ONE CHANGES ANYTHING:
#
#   (default)   AUDIT. Reads the inbound rules that allow 22/3389, whether Tailscale is running
#               and its 100.x address, and writes data\private_net.json. Changes nothing. Safe to
#               schedule; MT5-PrivateNetAudit runs it daily.
#   -Enforce    Adds ALLOW rules for 22/3389 from the tailnet (100.64.0.0/10) and $allow, then
#               disables (never deletes) every other inbound rule that allows 22/3389. Refuses
#               unless Tailscale reports Running with a 100.x address. BEFORE touching anything it
#               registers MT5-PrivateNetRollback to re-enable the disabled rules in
#               $rollbackMin minutes: if the operator is locked out, the box re-opens itself.
#   -Confirm    Run over the tailnet after -Enforce, once a new session is proven to work: removes
#               the rollback task, so the enforcement stands.
#
# NEVER SCHEDULE -Enforce. It is an operator's act with a dead-man rollback, run by hand.
# Undo at any time: -Rollback (re-enables the disabled rules and removes the tailnet rules).
param([switch]$Enforce, [switch]$Confirm, [switch]$Rollback)

$ErrorActionPreference = 'Stop'
$base = 'C:\opt\quant\desks\mt5'
$state = Join-Path $base 'data\private_net.json'
$tag = 'QuantPrivateNet'
$ports = @('22', '3389')
$tailnet = '100.64.0.0/10'
# The same allow-list ssh_guard.ps1 never bans: the build box, the Hetzner VPS, loopback.
$allow = @('169.58.159.142', '95.216.191.70', '127.0.0.1')
$rollbackMin = 15

function Get-TailscaleState {
  $exe = @('C:\Program Files\Tailscale\tailscale.exe', 'tailscale') |
         Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
  if (-not $exe) { return @{ installed = $false; running = $false; ip = $null } }
  $ip = (& $exe ip -4 2>$null | Select-Object -First 1)
  $st = (& $exe status --json 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue)
  return @{ installed = $true; running = ($st.BackendState -eq 'Running'); ip = $ip }
}

function Get-OpenRules {
  # Inbound, enabled ALLOW rules naming 22 or 3389 explicitly. Any-port rules (the terminal's)
  # are never touched, and neither are this script's own.
  $out = @()
  foreach ($r in Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True) {
    if ($r.Group -eq $tag) { continue }
    $pf = $r | Get-NetFirewallPortFilter
    if ($pf.Protocol -ne 'TCP') { continue }
    $lp = @($pf.LocalPort | ForEach-Object { "$_" })
    if (-not ($lp | Where-Object { $ports -contains $_ })) { continue }
    $af = $r | Get-NetFirewallAddressFilter
    $out += [pscustomobject]@{ name = $r.Name; display = $r.DisplayName; ports = ($lp -join ',');
                               remote = (@($af.RemoteAddress) -join ',') }
  }
  return $out
}

function Write-State($mode, $extra) {
  $ts = Get-TailscaleState
  $open = @(Get-OpenRules)
  $doc = [ordered]@{
    at = (Get-Date).ToUniversalTime().ToString('o'); mode = $mode
    tailscale = $ts; tailnet = $tailnet; allow = $allow; ports = $ports
    open_to_any = @($open | Where-Object { $_.remote -match 'Any' })
    other_allow_rules = @($open | Where-Object { $_.remote -notmatch 'Any' })
    enforced = [bool](Get-NetFirewallRule -Group $tag -ErrorAction SilentlyContinue)
    verdict = ''
  }
  foreach ($k in $extra.Keys) { $doc[$k] = $extra[$k] }
  $doc.verdict = if ($doc.open_to_any.Count -gt 0) { 'EXPOSED' }
                 elseif (-not $doc.enforced) { 'UNMEASURED' } else { 'PRIVATE' }
  $doc | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $state
  Write-Output ("private_net: " + $doc.verdict + " (" + $doc.open_to_any.Count + " rule(s) open to any)")
}

if ($Rollback) {
  Get-NetFirewallRule -Group "$tag-disabled" -ErrorAction SilentlyContinue |
    ForEach-Object { Enable-NetFirewallRule -Name $_.Name; Set-NetFirewallRule -Name $_.Name -Group '' }
  Get-NetFirewallRule -Group $tag -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  Unregister-ScheduledTask -TaskName 'MT5-PrivateNetRollback' -Confirm:$false -ErrorAction SilentlyContinue
  Write-State 'rollback' @{}
  exit 0
}

if ($Confirm) {
  Unregister-ScheduledTask -TaskName 'MT5-PrivateNetRollback' -Confirm:$false -ErrorAction SilentlyContinue
  Write-State 'confirmed' @{}
  exit 0
}

if (-not $Enforce) { Write-State 'audit' @{}; exit 0 }

$ts = Get-TailscaleState
if (-not $ts.running -or -not ($ts.ip -like '100.*')) {
  Write-State 'refused' @{ why = 'Tailscale is not Running with a 100.x address; enforcing would lock the tailnet out too' }
  exit 1
}

# The dead-man rollback goes in FIRST, so a lockout at any later step undoes itself.
$act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
  "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Rollback")
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes($rollbackMin)
Register-ScheduledTask -TaskName 'MT5-PrivateNetRollback' -Action $act -Trigger $trg `
  -User 'SYSTEM' -RunLevel Highest -Force | Out-Null

foreach ($p in $ports) {
  New-NetFirewallRule -DisplayName "$tag-$p" -Group $tag -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort $p -RemoteAddress (@($tailnet) + $allow) | Out-Null
}
foreach ($r in Get-OpenRules) {
  Disable-NetFirewallRule -Name $r.name
  Set-NetFirewallRule -Name $r.name -Group "$tag-disabled"
}
Write-State 'enforced-pending-confirm' @{ rollback_in_min = $rollbackMin }
Write-Output "Open a NEW session over the tailnet ($($ts.ip)) now, then run: install_private_net.ps1 -Confirm"
