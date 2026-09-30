$ErrorActionPreference = 'Stop'

$exe = 'C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe'
$log = 'C:\opt\quant\desks\mt5\logs\MT5-TerminalBoot.log'
$stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ssK'

$terminals = @(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" |
    Where-Object { $_.ExecutablePath -eq $exe } |
    Sort-Object CreationDate)

if ($terminals.Count -gt 1) {
    foreach ($duplicate in ($terminals | Select-Object -Skip 1)) {
        Stop-Process -Id $duplicate.ProcessId -Force -ErrorAction Stop
    }
    Add-Content -LiteralPath $log -Value "$stamp removed $($terminals.Count - 1) duplicate Fusion terminal(s); kept pid $($terminals[0].ProcessId)"
    exit 0
}

if ($terminals.Count -eq 1) {
    Add-Content -LiteralPath $log -Value "$stamp exactly one Fusion terminal ensured (pid $($terminals[0].ProcessId))"
    exit 0
}

if (-not (Test-Path -LiteralPath $exe)) {
    Add-Content -LiteralPath $log -Value "$stamp Fusion terminal executable missing: $exe"
    exit 2
}

Start-Process -FilePath $exe
Add-Content -LiteralPath $log -Value "$stamp no Fusion terminal was running; launched one"
exit 0
