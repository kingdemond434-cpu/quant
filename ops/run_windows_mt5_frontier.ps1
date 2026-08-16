param(
    [string]$CodeRoot = "C:\Users\dell\quant-conversion-fix",
    [string]$StateRoot = "C:\Users\dell\quant-platform",
    [string]$Python = "C:\Users\dell\AppData\Local\Programs\Python\Python312\python.exe",
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
$optionalFailures = @()
$lock = $null
$goldDeskWasRunning = $false

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
    $stepLog = Join-Path $env:TEMP "mt5-$name-$([Guid]::NewGuid().ToString('N')).log"
    try {
        # Do not pipe a MetaTrader-spawning process into Tee-Object: terminal64 inherits the pipe
        # handle and keeps it open after Python exits, which makes a completed step hang forever.
        & $action *> $stepLog
        $stepRc = $LASTEXITCODE
        Get-Content $stepLog | Tee-Object -FilePath $logPath -Append
        if ($stepRc -ne $null -and $stepRc -ne 0) {
            throw "$name exited $stepRc"
        }
        $steps[$name] = [ordered]@{state="PASS"; started_at=$stepStart.ToString("o"); finished_at=[DateTimeOffset]::UtcNow.ToString("o")}
    } catch {
        $steps[$name] = [ordered]@{state="FAIL"; started_at=$stepStart.ToString("o"); finished_at=[DateTimeOffset]::UtcNow.ToString("o"); error=$_.Exception.Message}
        throw
    } finally {
        Remove-Item -Force $stepLog -ErrorAction SilentlyContinue
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
    # The MT5 IPC wheel must run under the terminal owner's base interpreter. Reuse the quant
    # environment's pure-Python dependencies without invoking its launcher shim (which times out
    # against this portable investor terminal).
    $env:PYTHONPATH = "$CodeRoot;$StateRoot\.venv\Lib\site-packages"
    $env:PYTHONUNBUFFERED = "1"
    Set-Location $StateRoot
    Write-FrontierStatus "RUNNING" "read-only MT5 collection and research started"

    # MetaTrader's Python bridge permits one client per terminal. The installed VIG terminal is
    # the verified investor session owned by the PAPER gold sensor. Pause that worker, reuse the
    # same read-only session, and restore its supervisor before publication.
    $goldDesk = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -like "pythonw*.exe" -and $_.CommandLine -like "*-m golddesk.service*"
    }
    $goldDeskSupervisor = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "cmd.exe" -and $_.CommandLine -like "*run_desk.bat*"
    }
    if ($goldDesk -or $goldDeskSupervisor) {
        $goldDeskWasRunning = $true
        if ($goldDeskSupervisor) {
            $goldDeskSupervisor | ForEach-Object {
                Start-Process taskkill.exe -ArgumentList "/PID", $_.ProcessId, "/T", "/F" `
                    -Wait -WindowStyle Hidden
            }
        } else {
            $goldDesk | ForEach-Object {
                Start-Process taskkill.exe -ArgumentList "/PID", $_.ProcessId, "/T", "/F" `
                    -Wait -WindowStyle Hidden
            }
        }
        Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" | Where-Object {
            $_.ExecutablePath -eq $Terminal
        } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 5
    }

    Run-Step "ingest" {
        & $Python "$CodeRoot\scripts\ingest_history.py" --base "$StateRoot\data\lake" `
          --terminal $Terminal --allow-readonly-live --expected-server $ExpectedServer `
          --universe mt5-liquid-core --timeframes "D1,H4,H1,M15" --warmup-sleep 30 --tries 3
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

    # Full broker breadth is a Sunday expansion after the liquid core has already reached the
    # canonical pipeline. A native failure in a remote stock symbol is visible but cannot erase
    # the higher-value core cycle.
    if ((Get-Date).DayOfWeek -eq "Sunday") {
        try {
            Run-Step "full_broker_d1" {
                & $Python "$CodeRoot\scripts\ingest_history.py" --base "$StateRoot\data\lake" `
                  --terminal $Terminal --allow-readonly-live --expected-server $ExpectedServer `
                  --universe all --timeframes "D1" --warmup-sleep 30 --tries 2
            }
        } catch {
            $optionalFailures += "full_broker_d1: $($_.Exception.Message)"
        }
    }

    if ($goldDeskWasRunning) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", `
            '"C:\Users\dell\gold-desk\scripts\run_desk.bat"' -WindowStyle Hidden
        $goldDeskWasRunning = $false
        $steps["gold_desk_restart"] = [ordered]@{state="PASS"; finished_at=[DateTimeOffset]::UtcNow.ToString("o")}
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
    if ($optionalFailures.Count) {
        Write-FrontierStatus "DEGRADED" ($optionalFailures -join "; ")
    } else {
        Write-FrontierStatus "PASS" "fresh MT5 evidence published to canonical shadow pipeline"
    }
    exit 0
} catch {
    Write-FrontierStatus "FAIL" $_.Exception.Message
    Add-Content -Path $logPath -Value "[$([DateTimeOffset]::UtcNow.ToString('o'))] FAIL: $($_.Exception.Message)"
    exit 1
} finally {
    if ($goldDeskWasRunning) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", `
            '"C:\Users\dell\gold-desk\scripts\run_desk.bat"' -WindowStyle Hidden
    }
    if ($lock) { $lock.Dispose() }
}
