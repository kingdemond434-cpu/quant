# pull_from_vps.ps1 - Pull gate certificates from VPS to C:\opt\quant
# Runs as scheduled task every hour (offset from gauntlet at 00:45 UTC).
# Certificates persist here through sweeps — merge fix in place.
# Also pulls back after any gauntlet run so C:\opt\quant always has latest.

$ErrorActionPreference = "Continue"
$base = "C:\Users\dell\mt5-research"
$vps = "quant@95.216.191.70"
$vpsBase = "/home/quant/quant-platform/desks/mt5"
$winBase = "C:\opt\quant\desks\mt5"

# Pull UNIVERSAL_SURVIVORS.json (authority file)
$dest = "$winBase\reports"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
& scp -o ConnectTimeout=15 ${vps}:${vpsBase}/reports/UNIVERSAL_SURVIVORS.json "$dest/" 2>&1 | Out-Null

# Pull canon
$destData = "$winBase\data"
New-Item -ItemType Directory -Force -Path $destData | Out-Null
& scp -o ConnectTimeout=15 ${vps}:${vpsBase}/data/UNIVERSAL_SURVIVORS.canon.json "$destData/" 2>&1 | Out-Null

# Pull all universal_gates_*.json
& ssh -o ConnectTimeout=15 $vps "ls ${vpsBase}/reports/universal_gates_*.json 2>/dev/null" | ForEach-Object {
    $fname = [System.IO.Path]::GetFileName($_.Trim())
    & scp -o ConnectTimeout=15 ${vps}:${vpsBase}/reports/$fname "$dest/" 2>&1 | Out-Null
}

# Pull external gauntlet
& scp -o ConnectTimeout=15 ${vps}:${vpsBase}/reports/universal_gates_external.json "$dest/" 2>&1 | Out-Null

exit 0
