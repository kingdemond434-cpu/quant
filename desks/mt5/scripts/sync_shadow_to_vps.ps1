param(
    [string] $Vps = "quant@95.216.191.70",
    [string] $VpsDesk = "/home/quant/quant-platform/desks/mt5"
)
$ErrorActionPreference = "Stop"
$DeskRoot = Split-Path -Parent $PSScriptRoot
$Health = Join-Path $DeskRoot "reports\shadow\shadow_health.json"
if (-not (Test-Path $Health)) { throw "shadow health missing: $Health" }
$row = Get-Content $Health -Raw | ConvertFrom-Json
if ($row.status -ne "OPERATING" -or $row.represented_sleeves -ne $row.configured_sleeves) {
    throw "refusing incomplete shadow sync: status=$($row.status) represented=$($row.represented_sleeves)/$($row.configured_sleeves)"
}

$archive = Join-Path $env:TEMP ("mt5-shadow-{0}.tgz" -f $env:COMPUTERNAME)
$remote = "/tmp/mt5-shadow-$($env:COMPUTERNAME).tgz"
try {
    & tar -czf $archive -C $DeskRoot reports/shadow `
        data/universe/XAUUSD_M1.parquet data/universe/XAUUSD_M5.parquet `
        data/universe/XAUUSD_M15.parquet data/universe/XAUUSD_scalp_source.json
    if ($LASTEXITCODE -ne 0) { throw "tar failed rc=$LASTEXITCODE" }
    & scp -q -o BatchMode=yes -o ConnectTimeout=20 $archive "${Vps}:$remote"
    if ($LASTEXITCODE -ne 0) { throw "scp failed rc=$LASTEXITCODE" }
    & ssh -o BatchMode=yes -o ConnectTimeout=20 $Vps `
        "set -eu; mkdir -p '$VpsDesk/reports/shadow' '$VpsDesk/data/universe'; tar -xzf '$remote' -C '$VpsDesk'; rm -f '$remote'"
    if ($LASTEXITCODE -ne 0) { throw "remote extract failed rc=$LASTEXITCODE" }
    Write-Output ("shadow sync OK {0}/{1} at {2}" -f $row.represented_sleeves,
        $row.configured_sleeves, (Get-Date -Format o))
} finally {
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
}
