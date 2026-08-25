# sync_to_vps.ps1 - full-state push of the MT5 desk to the VPS brains.
# Runs from MT5Sync.cmd every 60s; executes the actual sync at most hourly
# (marker: data/sync_marker.json last_cycle; state: data/last_sync.json).
# Push everything: code, docs, reports, data registry, universe config, states,
# mandates. Excludes data/lake (large cache; tracked via data_registry.json).
# After upload, commits + pushes on the VPS repo so ALL brains see the state.

$ErrorActionPreference = "Continue"
$base = "C:\Users\dell\mt5-research"
$marker = Join-Path $base "data\sync_marker.json"
$last   = Join-Path $base "data\last_sync.json"
$bundle = Join-Path $env:TEMP "opencode\mt5_desk_bundle"
$vps = "quant@95.216.191.70:/home/quant/quant-platform/desks/mt5/"

$now = Get-Date
$lastSync = $null
if (Test-Path $last) {
    try { $lastSync = (Get-Content $last -Raw | ConvertFrom-Json).last_sync } catch {}
}
$due = $true
if ($lastSync) {
    try {
        $t = [datetime]::Parse($lastSync)
        $due = ($now - $t).TotalMinutes -ge 60
    } catch { $due = $true }
}
if (-not $due) { exit 0 }

# 1. Build the bundle (data files under bundle\data, dirs under bundle\<name>)
if (Test-Path $bundle) { Remove-Item -Recurse -Force $bundle }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null
foreach ($d in @("mt5desk", "research", "docs", "scripts", "reports")) {
    $src = Join-Path $base $d
    if (Test-Path $src) { Copy-Item -Path $src -Destination $bundle -Recurse -Force }
}
# NEVER overwrite VPS-live shadow state with this (often-stale) local copy
if (Test-Path "$bundle\reports\shadow") { Remove-Item -Recurse -Force "$bundle\reports\shadow" }
foreach ($f in @("AGENTS.md", "CLAUDE.md")) {
    $p = Join-Path $base $f
    if (Test-Path $p) { Copy-Item $p -Destination $bundle -Force }
}
$dataOut = Join-Path $bundle "data"
New-Item -ItemType Directory -Force -Path $dataOut | Out-Null
$src = Join-Path $base "data"
foreach ($d in @("universe", "states", "cot", "cot_tff", "cot_disagg", "lake",
                 "gateway_state.json","live_ledger.jsonl","regime_state.json",
                 "sleeves.json","terminal_path.txt","GATEWAY_PAUSED",
                 "frontier_inbox.json","sync_marker.json","data_registry.json",
                 "free_data_frontier.json","cot_tff.json","research_queue.json",
                 "macro_state.json","cross_asset_anchors.pkl","crowding_state.json",
                 "options_archive.parquet","news_state.json","HOLD_qquant_gates",
                 "HOLD_universal","HOLD_merge","HOLD_allocation","HOLD_qquant")) {
    $p = Join-Path $src $d
    if (Test-Path $p) { Copy-Item $p -Destination $dataOut -Recurse -Force }
}

# 2. Upload
$scp = Get-Command scp -ErrorAction SilentlyContinue
if (-not $scp) { exit 1 }
& $scp -r -q "$bundle\*" $vps 2>&1 | Out-Null

# 3. Commit + push on the VPS repo (whole-brain visibility)
$ssh = Get-Command ssh -ErrorAction SilentlyContinue
if ($ssh) {
    $cmd = "cd /home/quant/quant-platform && git add desks/mt5 && git commit -m 'mt5 desk hourly sync $(Get-Date -Format yyyy-MM-dd_HHmm)' -q && git push -q"
    & $ssh -o ConnectTimeout=20 quant@95.216.191.70 $cmd 2>&1 | Out-Null
}

# 4. Record
@{ last_sync = $now.ToString("o") } | ConvertTo-Json | Set-Content $last -Encoding utf8
exit 0