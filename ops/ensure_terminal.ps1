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

# Get-Process, never the CIM cmdlets: CIM has hung on the trading box (CLAUDE.md), and a
# watchdog that hangs is no watchdog. A terminal64 whose Path this account cannot read belongs
# to another account; it is NOT ours (counting it made any foreign MT5 refuse forever), so it is
# logged by session and left out.
function Get-FusionTerminals {
    @(Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $exe })
}
foreach ($u in @(Get-Process -Name 'terminal64' -ErrorAction SilentlyContinue |
        Where-Object { -not $_.Path })) {
    Add-Content -LiteralPath $log -Value "$stamp unreadable-path terminal in session $($u.SessionId) (pid $($u.Id)); not counted as Fusion"
}
$terminals = Get-FusionTerminals
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
    $local = @(Get-FusionTerminals | Where-Object { $_.SessionId -eq $session })
    if ($local.Count -ne 1) {
        Add-Content -LiteralPath $log -Value "$stamp launch did not establish exactly one terminal in interactive session $session"
        exit 2
    }
}

# The existing probe uses MT5 initialize/account_info only; no order permission.
# THE INTERPRETER IS RESOLVED, NEVER ASSUMED: a hard-coded path that is absent on this box reads
# "probe unavailable" forever and the watchdog can never pass. Order: the repo .venv, the per-user
# Python314 (Seal-IfClean.ps1's two candidates), then the machine-wide Program Files Python314
# (the path this script used to hard-code), then whatever `python` is on PATH.
$python = $null
foreach ($cand in @(
    (Join-Path $root '.venv\Scripts\python.exe'),
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
    'C:\Program Files\Python314\python.exe'
)) { if (Test-Path -LiteralPath $cand) { $python = $cand; break } }
if (-not $python) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
}
$probe = Join-Path $root 'desks\mt5\research\probe_terminal.py'
if (-not $python -or -not (Test-Path -LiteralPath $probe)) {
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

Add-Content -LiteralPath $log -Value "$stamp Fusion IPC/account probe passed in session $session (pid $($local[0].Id))"
# THE HEALTH FILE IS WRITTEN ON A PASSED PROBE ONLY. Every refusal above appends to the log, so the
# log's age says the task ran, not that the terminal is usable; organ_contract grades this file.
$okPath = Join-Path $root 'desks\mt5\data\terminal_boot_ok.json'
@{ at = (Get-Date).ToUniversalTime().ToString('o'); session = $session; pid = $local[0].Id;
   python = $python } | ConvertTo-Json -Compress | Set-Content -LiteralPath $okPath -Encoding UTF8
exit 0
