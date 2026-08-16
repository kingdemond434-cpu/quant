param(
    [string]$CodeRoot = "C:\Users\dell\quant-conversion-fix",
    [string]$StateRoot = "C:\Users\dell\quant-platform",
    [string]$Python = "C:\Users\dell\quant-platform\.venv\Scripts\python.exe",
    [string]$Terminal = "C:\Program Files\VIG Group MT5 Terminal\terminal64.exe",
    [string]$ExpectedServer = "VantageMarkets-Live 14",
    [string]$SshKey = "$env:USERPROFILE\.ssh\id_ed25519",
    [string]$Vps = "quant@95.216.191.70"
)

$ErrorActionPreference = "Stop"
$statusPath = Join-Path $StateRoot "reports\mt5_frontier_windows.json"
$logPath = Join-Path $StateRoot "logs\mt5_frontier_windows.log"
$lockPath = Join-Path $StateRoot "data\.mt5_frontier_windows.lock"
$started = [DateTimeOffset]::UtcNow
$steps = [ordered]@{}
$lock = $null

New-Item -ItemType Directory -Force (Split-Path $statusPath), (Split-Path $logPath), (Split-Path $lockPath) | Out-Null

function Write-FrontierStatus([string]$state, [string]$reason) {
    $payload = [ordered]@{
        schema_version = 1
        state = $state
        reason = $reason
        started_at = $started.ToString("o")
        updated_at = [DateTimeOffset]::UtcNow.ToString("o")
        code_root = $CodeRoot
        state_root = $StateRoot
        mode = "MT5_INVESTOR_READONLY_RESEARCH"
        execution_authority = $false
        survival_gates_bypassed = $false
        steps = $steps
    }
    $temp = "$statusPath.tmp"
    $payload | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $temp
    Move-Item -Force $temp $statusPath
}

function Run-Step([string]$name, [scriptblock]$action) {
    $stepStart = [DateTimeOffset]::UtcNow
    try {
        & $action *>&1 | Tee-Object -FilePath $logPath -Append
        if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
            throw "$name exited $LASTEXITCODE"
        }
        $steps[$name] = [ordered]@{state="PASS"; started_at=$stepStart.ToString("o"); finished_at=[DateTimeOffset]::UtcNow.ToString("o")}
    } catch {
        $steps[$name] = [ordered]@{state="FAIL"; started_at=$stepStart.ToString("o"); finished_at=[DateTimeOffset]::UtcNow.ToString("o"); error=$_.Exception.Message}
        throw
    }
}

try {
    $lock = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    Write-FrontierStatus "SKIPPED_LOCKED" "another MT5 frontier cycle owns the lock"
    exit 0
}

try {
    if (!(Test-Path $Python) -or !(Test-Path $Terminal) -or !(Test-Path $CodeRoot)) {
        throw "required Python, MT5 terminal, or code root is missing"
    }
    $env:PYTHONPATH = $CodeRoot
    Set-Location $StateRoot
    Write-FrontierStatus "RUNNING" "read-only MT5 collection and research started"

    Run-Step "ingest" {
        & $Python "$CodeRoot\scripts\ingest_history.py" --base "$StateRoot\data\lake" `
          --terminal $Terminal --allow-readonly-live --expected-server $ExpectedServer `
          --timeframes "D1,H4,H1,M15" --warmup-sleep 20 --tries 8
    }
    foreach ($tf in @("D1", "H4", "H1", "M15")) {
        $bars = if ($tf -eq "M15") { 30000 } elseif ($tf -eq "H1") { 20000 } else { 8000 }
        Run-Step "autodiscovery_$tf" {
            & $Python "$CodeRoot\scripts\run_autodiscovery.py" --once `
              --terminal $Terminal --allow-readonly-live --expected-server $ExpectedServer `
              --universe mt5-liquid-core --timeframe $tf --bars $bars `
              --db "$StateRoot\data\sor_mt5_$($tf.ToLower()).sqlite" `
              --report-dir "$StateRoot\reports\autodiscovery\mt5_$tf"
        }
    }

    # Publish only the broker-universe research lake and compact evidence, never credentials or
    # terminal state.  The VPS remains the canonical validator/shadow consumer.
    $archive = Join-Path $env:TEMP "mt5-frontier-$([Guid]::NewGuid().ToString('N')).tar.gz"
    Run-Step "package" {
        & tar -czf $archive -C $StateRoot reports/data_coverage.json reports/mt5_frontier_windows.json `
          reports/autodiscovery data/lake/bronze/fx data/lake/bronze/metal `
          data/lake/bronze/energy data/lake/bronze/index
    }
    Run-Step "publish_to_vps" {
        & scp -q -i $SshKey -o IdentitiesOnly=yes -o BatchMode=yes $archive "$Vps`:/tmp/mt5-frontier.tar.gz"
        & ssh -i $SshKey -o IdentitiesOnly=yes -o BatchMode=yes $Vps `
          "cd /home/quant/quant-platform && tar -xzf /tmp/mt5-frontier.tar.gz && rm -f /tmp/mt5-frontier.tar.gz && .venv/bin/python scripts/run_crossasset_shadow.py"
    }
    Remove-Item -Force $archive -ErrorAction SilentlyContinue
    Write-FrontierStatus "PASS" "fresh MT5 evidence published to canonical shadow pipeline"
    exit 0
} catch {
    Write-FrontierStatus "FAIL" $_.Exception.Message
    Add-Content -Path $logPath -Value "[$([DateTimeOffset]::UtcNow.ToString('o'))] FAIL: $($_.Exception.Message)"
    exit 1
} finally {
    if ($lock) { $lock.Dispose() }
}
