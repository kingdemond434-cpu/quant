$ErrorActionPreference = "Stop"
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$QuantRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $env:USERPROFILE ".venv\Scripts\python.exe"
$Fetch = Join-Path $QuantRoot "desks\mt5\research\fetch_gold_scalp.py"
$Shadow = Join-Path $QuantRoot "desks\mt5\research\scalp_shadow.py"
$Log = Join-Path $QuantRoot "desks\mt5\logs\scalp_shadow.log"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime missing: $Python"
}

$terminals = @(
    "C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe",
    "C:\Program Files\VIG Group MT5 Terminal\terminal64.exe"
)
$fetched = $false
foreach ($terminal in $terminals) {
    if (-not (Test-Path -LiteralPath $terminal)) { continue }
    $fetchRc = 1
    try {
        # A present but logged-out Fusion terminal is an expected failover condition, not a
        # reason to abort before the read-only proxy terminal is tried.
        & $Python $Fetch --terminal $terminal --bars 90000 *>> $Log
        $fetchRc = $LASTEXITCODE
    }
    catch {
        $_ | Out-String | Add-Content -LiteralPath $Log
        $fetchRc = 1
    }
    if ($fetchRc -eq 0) {
        $fetched = $true
        break
    }
}
if (-not $fetched) {
    throw "No read-only MT5 terminal supplied XAUUSD intraday history"
}

& $Python $Shadow *>> $Log
if ($LASTEXITCODE -ne 0) {
    throw "Gold scalp shadow failed with rc=$LASTEXITCODE"
}
