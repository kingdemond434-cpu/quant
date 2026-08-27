# STALL WATCHDOG -- nothing on this box is ever stuck, stacked, or disabled for long.
# (principal 2026-08-27: "nothing should ever be stalled etc, I won't be here to tell you")
#
# Runs every 10 minutes as MT5-StallWatch. Three failure shapes it heals, all measured tonight:
#   STACKED  - the same research script running more than once (a 15-min trigger piling onto a
#              slow pass; state files then race and the last writer erases the first's work).
#              Heal: kill every instance but the OLDEST parent.
#   STALLED  - a process alive >15 min whose CPU time advanced <5s since the last check
#              (a parent whose pool died, an MT5 call that never returns). Heal: kill it;
#              every research task is scheduled with StartWhenAvailable, so work resumes on
#              the next trigger with no human.
#   DISABLED - a task flipped Disabled by a Stop-Process race (result 267014, seen twice).
#              Heal: Enable-ScheduledTask.
# The money path (gateway, deadman) is NEVER touched: research only.
# Verdicts land in data\stall_watch.json so the desk-state builder can carry them to the
# dashboard pulse -- healing that nobody can see is healing nobody can trust.

$ErrorActionPreference = 'SilentlyContinue'
$base = 'C:\opt\quant\desks\mt5'
$stateFile = Join-Path $base 'data\stall_watch.json'
$patterns = @('external_gauntlet', 'shadow_cycle', 'edge_search', 'expand_universe',
              'moat_silver', 'orthogonal_sweep', 'qquant_gates', 'universal_gate')
$researchTasks = @('MT5-Gauntlet', 'MT5-Shadow', 'MT5-Hourly', 'MT5-MoatSilver',
                   'MT5-MoatRecorder', 'MT5-QQuantShadow', 'MT5-UniversalGate',
                   'MT5-QQuantGatesCertify', 'MT5-ResearchSupervisor')

$prev = @{}
if (Test-Path $stateFile) {
  try { (Get-Content $stateFile -Raw | ConvertFrom-Json).procs.PSObject.Properties |
        ForEach-Object { $prev[$_.Name] = $_.Value } } catch {}
}

$now = Get-Date
$actions = @()
$procsOut = @{}

foreach ($pat in $patterns) {
  $procs = Get-CimInstance Win32_Process -Filter "Name like 'py%'" |
           Where-Object { $_.CommandLine -match $pat } | Sort-Object CreationDate
  if (-not $procs) { continue }

  # STACKED: keep the oldest parent; kill the rest UNLESS they are its own children
  $keeper = $procs[0]
  foreach ($p in ($procs | Select-Object -Skip 1)) {
    if ($p.ParentProcessId -ne $keeper.ProcessId) {
      Stop-Process -Id $p.ProcessId -Force
      $actions += "STACKED ${pat}: killed duplicate pid $($p.ProcessId) (kept oldest $($keeper.ProcessId))"
    }
  }

  # STALLED: CPU barely moved since the previous watchdog pass
  $gp = Get-Process -Id $keeper.ProcessId
  if ($gp) {
    $cpu = $gp.TotalProcessorTime.TotalSeconds
    $key = "$pat.$($keeper.ProcessId)"
    $ageMin = ($now - $keeper.CreationDate).TotalMinutes
    if ($prev.ContainsKey($key)) {
      $delta = $cpu - [double]$prev[$key].cpu
      $sinceMin = ($now - [datetime]$prev[$key].at).TotalMinutes
      if ($ageMin -gt 15 -and $sinceMin -ge 8 -and $delta -lt 5) {
        Stop-Process -Id $keeper.ProcessId -Force
        # children die with the parent or become the next pass's STACKED kill
        $actions += "STALLED ${pat}: pid $($keeper.ProcessId) alive $([math]::Round($ageMin))m, CPU +$([math]::Round($delta,1))s in $([math]::Round($sinceMin))m -- killed; next trigger resumes"
        continue
      }
    }
    $procsOut[$key] = @{ cpu = $cpu; at = $now.ToString('o') }
  }
}

# DISABLED research tasks come back on
foreach ($tn in $researchTasks) {
  $st = (schtasks /Query /TN $tn /FO CSV 2>$null | ConvertFrom-Csv).Status
  if ($st -eq 'Disabled') {
    Enable-ScheduledTask -TaskName $tn | Out-Null
    $actions += "DISABLED ${tn}: re-enabled"
  }
}

@{ checked_at = $now.ToUniversalTime().ToString('o'); actions = $actions; procs = $procsOut } |
  ConvertTo-Json -Depth 4 | Set-Content $stateFile

if ($actions) { $actions | ForEach-Object { "$($now.ToUniversalTime().ToString('u')) $_" } }
else { "$($now.ToUniversalTime().ToString('u')) all research processes healthy" }
