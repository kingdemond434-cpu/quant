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

# TASK EXISTENCE (gap 3). Disabled and failing tasks heal above -- a task DELETED outright
# vanishes with nothing to heal. The required set is declared here and any missing task is
# reported by name; re-registration needs its exact action, which lives in ops/, so this
# reports rather than guesses (a wrong re-registration is worse than a missing task).
$requiredTasks = @('MT5-Gauntlet','MT5-Shadow','MT5-Hourly','MT5-DeskState','MT5-MoatRecorder',
                   'MT5-MoatSilver','MT5-StallWatch','MT5-Universe','MT5-ShadowSync')
$present = (schtasks /Query /FO CSV 2>$null | ConvertFrom-Csv | ForEach-Object { $_.TaskName -replace '^\\','' })
foreach ($rt in $requiredTasks) {
  if ($present -notcontains $rt) {
    $actions += "TASK MISSING: $rt is not registered at all -- re-register from ops/ (deletion, not failure)"
  }
}

# PER-SYMBOL FEED LAG (gap 2). A single symbol's bars can fall hours behind while the terminal
# looks healthy overall -- USDZAR sat 21h stale and only a log line knew. Any traded symbol
# whose newest H1 bar is >6h old during the trading week is named; the fixer is re-selecting it
# in MarketWatch, which is what makes the terminal stream it again.
try {
  $uniDir = 'C:\opt\quant\desks\mt5\data\universe'
  $now = (Get-Date).ToUniversalTime()
  if ($now.DayOfWeek -ne 'Saturday' -and $now.DayOfWeek -ne 'Sunday') {
    # ONLY SYMBOLS THAT CARRY A LIVE CLOCK. The 251-symbol registry is refreshed DAILY by
    # design (equity/index CFDs), so a blanket 6h rule pages on ~200 files that are working
    # exactly as intended -- a watchdog that cries every pass gets ignored, which is worse than
    # no watchdog. What actually starves a forward clock is ITS OWN symbol going stale, so the
    # check is scoped to symbols under evaluation right now.
    $watched = @()
    try {
      $ss = Get-Content 'C:\opt\quant\desks\mt5\reports\shadow\shadow_state.json' -Raw |
            ConvertFrom-Json
      foreach ($p in $ss.PSObject.Properties) {
        if ($p.Value.status -eq 'ACTIVE') { $watched += ($p.Name -split '\.')[0] }
      }
    } catch { }
    $watched = $watched | Sort-Object -Unique
    $laggy = @()
    foreach ($sym in $watched) {
      $f = Get-Item ($uniDir + '\' + $sym + '_H1.parquet') -ErrorAction SilentlyContinue
      if ($f -and $f.LastWriteTimeUtc -lt $now.AddHours(-6)) { $laggy += $sym }
    }
    if ($laggy.Count -gt 0) {
      $actions += "FEED LAG: " + $laggy.Count + " CLOCKED symbol(s) >6h stale: " + ($laggy -join ',')
      foreach ($sym in $laggy) {
        try { py -3 -c "import MetaTrader5 as m; m.initialize(); m.symbol_select('$sym', True); m.shutdown()" 2>$null } catch { }
      }
      $actions += "FEED LAG fixer: re-selected " + $laggy.Count + " symbol(s) in MarketWatch"
    }
  }
} catch { }

# UNIVERSE REGISTRY RATCHET (desk side). A rogue writer keeps rebuilding universe.json from
# the terminal's 23 MarketWatch rows (three strikes on 2026-08-27; the last one blocked both
# gap-decay forward clocks with KeyError: EURZAR while every fence read green). The VPS repair
# organ ratchets its own copy; THIS is the desk's local ratchet -- rows may never shrink below
# the canon superset, and a shrunken file is restored from canon within one 10-minute pass.
$uniPath = 'C:\opt\quant\desks\mt5\data\universe\universe.json'
$canPath = 'C:\opt\quant\desks\mt5\data\universe\universe.canon.json'
try {
  $uni = Get-Content $uniPath -Raw -ErrorAction Stop | ConvertFrom-Json
  $can = Get-Content $canPath -Raw -ErrorAction Stop | ConvertFrom-Json
  $nU = ($uni.PSObject.Properties | Measure-Object).Count
  $nC = ($can.PSObject.Properties | Measure-Object).Count
  if ($nU -lt $nC) {
    Copy-Item $canPath $uniPath -Force
    $actions += "UNIVERSE: registry shrank to $nU rows (canon $nC) -- restored from canon"
  } elseif ($nU -gt $nC) {
    Copy-Item $uniPath $canPath -Force    # the ratchet grows with the registry
  }
} catch { $actions += "UNIVERSE: guard could not read registry/canon ($_)" }

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
