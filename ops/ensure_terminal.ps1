$ErrorActionPreference = 'Stop'

$exe = 'C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe'
$root = 'C:\opt\quant'
$log = Join-Path $root 'desks\mt5\logs\MT5-TerminalBoot.log'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'
$session = (Get-Process -Id $PID).SessionId

# A PID is not proof of a usable terminal. On 2026-10-02 the sole Fusion
# process was windowless in Session 0 while every MT5 API call timed out.
# Never launch a GUI terminal from that non-interactive session.
if ($session -eq 0) {
    Add-Content -LiteralPath $log -Value "$stamp watchdog in Session 0; refusing a headless launch or false health verdict"
    exit 2
}

$terminals = @(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" |
    Where-Object { $_.ExecutablePath -eq $exe } |
    Sort-Object CreationDate)
$local = @($terminals | Where-Object { $_.SessionId -eq $session })

# A terminal in another session may own live state. Refuse to kill it or launch
# another on the same data directory without controlled reconciliation.
if ($terminals.Count -gt 0 -and $local.Count -eq 0) {
    $sessions = ($terminals | ForEach-Object { $_.SessionId }) -join ','
    Add-Content -LiteralPath $log -Value "$stamp terminal in session(s) $sessions, watchdog in $session; IPC unverified, controlled recovery required"
    exit 2
}
if ($local.Count -gt 1) {
    Add-Content -LiteralPath $log -Value "$stamp $($local.Count) Fusion terminals in session $session; refusing to guess which owns live state"
    exit 2
}
if ($terminals.Count -gt 1) {
    Add-Content -LiteralPath $log -Value "$stamp Fusion terminals span sessions; refusing automatic termination of an unverified owner"
    exit 2
}

if ($local.Count -eq 0) {
    if (-not (Test-Path -LiteralPath $exe)) {
        Add-Content -LiteralPath $log -Value "$stamp Fusion terminal executable missing: $exe"
        exit 2
    }
    Start-Process -FilePath $exe -WindowStyle Hidden
    Start-Sleep -Seconds 8
    $local = @(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" |
        Where-Object { $_.ExecutablePath -eq $exe -and $_.SessionId -eq $session })
    if ($local.Count -ne 1) {
        Add-Content -LiteralPath $log -Value "$stamp launch did not establish exactly one terminal in interactive session $session"
        exit 2
    }
}

# The existing probe uses MT5 initialize/account_info only; no order permission.
$python = 'C:\Program Files\Python314\python.exe'
$probe = Join-Path $root 'desks\mt5\research\probe_terminal.py'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $probe)) {
    Add-Content -LiteralPath $log -Value "$stamp read-only Fusion IPC probe unavailable"
    exit 2
}
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue' # native stderr is data; the exit code is the verdict
try {
    $probeOutput = & $python -u $probe 2>&1 | Out-String
    $probeCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorAction
}
if ($probeCode -ne 0) {
    $reason = ($probeOutput -split "`n" | Where-Object { $_ -match 'init:|last_error|Traceback|Error' } | Select-Object -First 1)
    Add-Content -LiteralPath $log -Value "$stamp Fusion IPC/account probe failed rc=$probeCode session=$session $reason"
    exit 2
}

Add-Content -LiteralPath $log -Value "$stamp Fusion IPC/account probe passed in session $session (pid $($local[0].ProcessId))"
exit 0
