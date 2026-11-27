<#
.SYNOPSIS
    BOOT r23 + r24, the owner's one install: the guard's folder and the run-as migrator.
    Run once, elevated, from the boot checkout:  powershell -ExecutionPolicy Bypass -File ops\box_git\install_guard.ps1

    zuck 2026-11-27 13:13Z: "An independent, protected automated checker validates it ... You only
    intervene when the system needs to change its fundamental authority or protected safeguards."

    WHAT IT DOES (logged to C:\ProgramData\QuantBox\logs\install_guard_<stamp>.log); it changes no
    trading task, no terminal and nothing in C:\opt\quant except one ACL grant to quantrun:
      1. Refuses unless elevated.
      2. C:\ProgramData\QuantBox\guard (+ verdicts, runas): Administrators and SYSTEM Full,
         quantgate Modify (the loop writes verdicts and the merge ledger), quantci and quantrun
         denied.
      3. Creates `quantrun` (no administrator) with batch logon, Modify on C:\opt\quant, read on
         the python the gateway uses, and WRITE DENIED on guard, trust, tokens, forge, inbox, each
         terminal's install folder and each terminal's data folder.
      4. Copies the migrator (runas_plan.py, runas_probe.py, migrate.ps1) from this checkout into
         guard\runas and records each file's SHA-256 in guard\runas\PINNED.json.
      5. Writes venues.json: each running terminal's exe, its data folder (from origin.txt) and
         the LAST TWO DIGITS of its login (from the window title), nothing more.
      6. Registers QuantGuard-RunAs (SYSTEM, every 5 min) and runs it once. From here the migrator
         probes, waits for the weekend closure, moves, watches and proves on its own.
#>
$ErrorActionPreference = 'Stop'
$src   = Split-Path -Parent $MyInvocation.MyCommand.Path            # ...\ops\box_git
$QB    = 'C:\ProgramData\QuantBox'
$Guard = Join-Path $QB 'guard'
$Runas = Join-Path $Guard 'runas'
$Live  = 'C:\opt\quant'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$null  = New-Item -ItemType Directory -Force -Path (Join-Path $QB 'logs')
$log   = Join-Path $QB "logs\install_guard_$stamp.log"
function Say([string] $m) { $l = "{0}  {1}" -f (Get-Date).ToUniversalTime().ToString('HH:mm:ss'), $m; Write-Host $l; Add-Content -LiteralPath $log -Value $l }
function Stop-Here([string] $why) { Say "STOPPED: $why"; exit 1 }

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Stop-Here 'run this elevated (Run as administrator)' }

# 1-2. the guard's folder
$null = New-Item -ItemType Directory -Force -Path $Guard, (Join-Path $Guard 'verdicts'), $Runas
& icacls $Guard /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "quantgate:(OI)(CI)M" | Out-Null
& icacls $Runas /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "quantgate:(OI)(CI)RX" | Out-Null
& icacls $Guard /deny "quantci:(OI)(CI)F" | Out-Null
Say "guard folder ready: $Guard (Admins/SYSTEM full, quantgate modify, quantci denied)"

# 3. quantrun
$RunUser = 'quantrun'
if (-not (Get-LocalUser -Name $RunUser -ErrorAction SilentlyContinue)) {
    $b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    $pw = ConvertTo-SecureString ([Convert]::ToBase64String($b)) -AsPlainText -Force
    New-LocalUser -Name $RunUser -Password $pw -PasswordNeverExpires -UserMayNotChangePassword `
        -Description 'Quant box trading code (no admin)' | Out-Null
    $pw = $null
    Say "created $RunUser (no administrator; S4U tasks need no stored password)"
}
$sid = (New-Object Security.Principal.NTAccount $RunUser).Translate([Security.Principal.SecurityIdentifier]).Value
$inf = Join-Path $env:TEMP 'qr_rights.inf'; $db = Join-Path $env:TEMP 'qr_rights.sdb'
& secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
$rights = Get-Content -LiteralPath $inf
if (-not ($rights -match "SeBatchLogonRight.*\*$sid")) {
    $rights = $rights -replace '^(SeBatchLogonRight\s*=\s*.*)$', "`$1,*$sid"
    if (-not ($rights -match '^SeBatchLogonRight')) { $rights += "SeBatchLogonRight = *$sid" }
    Set-Content -LiteralPath $inf -Value $rights
    & secedit /configure /db $db /cfg $inf /areas USER_RIGHTS | Out-Null
}
Remove-Item -LiteralPath $inf, $db -Force -ErrorAction SilentlyContinue

# the python the gateway runs (from its own task), which quantrun must be able to read
$gw = Get-ScheduledTask -TaskName 'MT5-Gateway' -ErrorAction SilentlyContinue
$py = $null
if ($gw) {
    $blob = ($gw.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join ' '
    $m = [regex]::Match($blob, '[A-Za-z]:\\[^"&>|]*?python\.exe')
    if ($m.Success) { $py = $m.Value }
    elseif ($blob -match '(Python3\d+\\python\.exe)') {
        $cand = @("C:\$($Matches[1])", "C:\Program Files\$($Matches[1])", "$env:LOCALAPPDATA\Programs\Python\$($Matches[1])")
        $py = $cand | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
}
if (-not $py) { Stop-Here 'could not find the python MT5-Gateway runs' }
Set-Content -LiteralPath (Join-Path $Runas 'python.txt') -Value $py -Encoding ascii
& icacls (Split-Path -Parent $py) /grant "${RunUser}:(OI)(CI)RX" | Out-Null
Set-Content -LiteralPath (Join-Path $Runas 'live_tree.txt') -Value $Live -Encoding ascii
& icacls $Live /grant "${RunUser}:(OI)(CI)M" | Out-Null
Say "python: $py (quantrun may read it); quantrun may modify $Live"

# 5. venues: running terminals, their data folders, login suffixes
$venues = @()
$dataRoot = 'C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal'
foreach ($p in Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -ne 0 -and $_.Path }) {
    $dirs = @(Get-ChildItem -LiteralPath $dataRoot -Directory -ErrorAction SilentlyContinue | Where-Object {
        $o = Join-Path $_.FullName 'origin.txt'
        (Test-Path -LiteralPath $o) -and ((Get-Content -LiteralPath $o -Raw -Encoding Unicode).Trim() -eq (Split-Path -Parent $p.Path))
    } | ForEach-Object { $_.FullName })
    $digits = [regex]::Match("$($p.MainWindowTitle)", '\d{4,}').Value
    if (-not $digits) { Stop-Here "terminal $($p.Path): no login in its window title; cannot set the probe's expectation" }
    $name = if ($p.Path -match 'FTMO') { 'ftmo' } elseif ($p.Path -match 'Fusion') { 'fusion' } else { "t$($p.Id)" }
    $venues += @{ name = $name; exe = $p.Path; install = (Split-Path -Parent $p.Path); data_dirs = $dirs
                  expect = $digits.Substring($digits.Length - 2) }
    Say "venue $name : $($p.Path), $($dirs.Count) data folder(s), login ending $($digits.Substring($digits.Length - 2))"
}
if ($venues.Count -eq 0) { Stop-Here 'no interactive terminal running; start them first' }
$venues | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Runas 'venues.json') -Encoding utf8

# write denied for quantrun (Audit MF-A, Q2)
$deny = @($Guard, (Join-Path $QB 'trust'), (Join-Path $QB 'tokens'), (Join-Path $QB 'forge'), (Join-Path $QB 'inbox'), 'C:\opt\bridge')
foreach ($v in $venues) { $deny += $v.install; $deny += $v.data_dirs }
foreach ($d in $deny) { if (Test-Path -LiteralPath $d) { & icacls $d /deny "${RunUser}:(OI)(CI)(W,D,DC,WDAC,WO)" | Out-Null; Say "write denied to quantrun: $d" } }

# 4. the pinned migrator
$pinned = @{}
foreach ($f in @('runas_plan.py', 'runas_probe.py', 'runas\migrate.ps1')) {
    $from = Join-Path $src $f
    if (-not (Test-Path -LiteralPath $from)) { Stop-Here "missing $from" }
    $to = Join-Path $Runas (Split-Path -Leaf $f)
    Copy-Item -LiteralPath $from -Destination $to -Force
    $pinned[(Split-Path -Leaf $f)] = (Get-FileHash -LiteralPath $to -Algorithm SHA256).Hash.ToLower()
}
$pinned | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Runas 'PINNED.json') -Encoding utf8
Say ("pinned: " + (($pinned.GetEnumerator() | ForEach-Object { "$($_.Key) $($_.Value.Substring(0,12))" }) -join ', '))

# 6. the migrator's task
$act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Runas\migrate.ps1`""
$trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$set = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable
$pr  = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'QuantGuard-RunAs' -Action $act -Trigger $trg -Settings $set -Principal $pr -Force | Out-Null
Start-ScheduledTask -TaskName 'QuantGuard-RunAs'
Say 'QuantGuard-RunAs registered (SYSTEM, every 5 min) and started: it probes now, moves only in the weekend closure'
Say "log: $log"
