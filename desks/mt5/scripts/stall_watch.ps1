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
# one snapshot of every python process, so child CPU can be attributed to its parent's tree
$allProcs = @(Get-CimInstance Win32_Process -Filter "Name like 'py%'")

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

  # STALLED: the WHOLE PROCESS TREE barely moved since the previous pass.
  # Measuring only the parent was a self-inflicted wound (2026-08-27): a multiprocessing search
  # parent sits idle by design while its worker children compute, so it read as "CPU +0s in 10m"
  # and this watchdog killed every edge_search and orthogonal_sweep at ~20 minutes -- minutes
  # before each would have written its artifact. A job is stalled only when NOTHING in its tree
  # is working, so children's CPU counts toward the parent's liveness.
  $gp = Get-Process -Id $keeper.ProcessId
  if ($gp) {
    $cpu = $gp.TotalProcessorTime.TotalSeconds
    $kids = @($allProcs | Where-Object { $_.ParentProcessId -eq $keeper.ProcessId })
    foreach ($k in $kids) {
      $kp = Get-Process -Id $k.ProcessId -ErrorAction SilentlyContinue
      if ($kp) { $cpu += $kp.TotalProcessorTime.TotalSeconds }
    }
    $key = "$pat.$($keeper.ProcessId)"
    $ageMin = ($now - $keeper.CreationDate).TotalMinutes
    if ($prev.ContainsKey($key)) {
      $delta = $cpu - [double]$prev[$key].cpu
      $sinceMin = ($now - [datetime]$prev[$key].at).TotalMinutes
      # 40-minute floor and a 25-minute quiet window: the measured searches run 20-30 minutes,
      # so anything tighter kills real work. A truly hung job still dies, just not a slow one.
      if ($ageMin -gt 40 -and $sinceMin -ge 25 -and $delta -lt 5) {
        Stop-Process -Id $keeper.ProcessId -Force
        # children die with the parent or become the next pass's STACKED kill
        $actions += "STALLED ${pat}: pid $($keeper.ProcessId) alive $([math]::Round($ageMin))m, TREE CPU +$([math]::Round($delta,1))s in $([math]::Round($sinceMin))m -- killed; next trigger resumes"
        continue
      }
    }
    $procsOut[$key] = @{ cpu = $cpu; at = $now.ToString('o') }
  }
}

# DISABLED research tasks come back on; a task whose last TWO results failed while idle is
# re-run (IgnoreNew makes the retry safe; a task that fails again surfaces on the next pass).
foreach ($tn in $researchTasks) {
  $q = schtasks /Query /TN $tn /FO CSV /V 2>$null | ConvertFrom-Csv
  if (-not $q) { continue }
  if ($q.Status -eq 'Disabled') {
    Enable-ScheduledTask -TaskName $tn | Out-Null
    $actions += "DISABLED ${tn}: re-enabled"
  }
  $lr = [int64]($q.'Last Result')
  if ($q.Status -eq 'Ready' -and $lr -ne 0 -and $lr -ne 267009 -and $lr -ne 267014) {
    $failKey = "fail.$tn"
    if ($prev.ContainsKey($failKey) -and [int64]$prev[$failKey].cpu -eq $lr) {
      schtasks /Run /TN $tn | Out-Null
      $actions += "FAILING ${tn}: last result $lr twice in a row -- re-run"
    }
    $procsOut[$failKey] = @{ cpu = $lr; at = $now.ToString('o') }
  }
}

# DESK DISK FLOOR. A full C: kills the terminal, every task and every artifact write at once,
# silently. Below 5GB: prune the two safe reclaim pools -- logs older than 14 days and the
# gauntlet series cache (pure recompute) -- and REPORT. Below 2GB after pruning: loud breach
# line the desk-state builder carries to the dashboard.
$free = (Get-PSDrive C).Free / 1GB
if ($free -lt 5) {
  Get-ChildItem 'C:\opt\quant\desks\mt5\logs' -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
    ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
  Remove-Item 'C:\opt\quant\desks\mt5\reports\gauntlet_cache\*' -Force -ErrorAction SilentlyContinue
  $free2 = (Get-PSDrive C).Free / 1GB
  $actions += "DISK: C: was $([math]::Round($free,1))GB free -- pruned old logs + series cache -> $([math]::Round($free2,1))GB"
  if ($free2 -lt 2) { $actions += "DISK CRITICAL: $([math]::Round($free2,1))GB free AFTER pruning -- needs a human decision" }
}

@{ checked_at = $now.ToUniversalTime().ToString('o'); actions = $actions; procs = $procsOut; free_gb = [math]::Round((Get-PSDrive C).Free / 1GB, 1) } |
  ConvertTo-Json -Depth 4 | Set-Content $stateFile

if ($actions) { $actions | ForEach-Object { "$($now.ToUniversalTime().ToString('u')) $_" } }
else { "$($now.ToUniversalTime().ToString('u')) all research processes healthy" }
