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

# 1. Build the bundle (Copy-Item; robocopy file-source is a no-op)
if (Test-Path $bundle) { Remove-Item -Recurse -Force $bundle }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null
foreach ($d in @("mt5desk", "research", "docs", "scripts", "reports", "data")) {
    $src = Join-Path $base $d
    if (Test-Path $src) {
        if ($d -eq "data") {
            Copy-Item -Path (Join-Path $src "universe") -Destination $bundle -Recurse -Force
            Copy-Item -Path (Join-Path $src "states") -Destination $bundle -Recurse -Force
            foreach ($f in @("gateway_state.json","live_ledger.jsonl","regime_state.json",
                             "sleeves.json","terminal_path.txt","GATEWAY_PAUSED",
                             "frontier_inbox.json","sync_marker.json","data_registry.json",
                             "free_data_frontier.json","cot","cot_tff","cot_tff.json")) {
                $p = Join-Path $src $f
                if (Test-Path $p) { Copy-Item $p -Destination $bundle -Recurse -Force }
            }
        } else {
            Copy-Item -Path $src -Destination $bundle -Recurse -Force
        }
    }
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