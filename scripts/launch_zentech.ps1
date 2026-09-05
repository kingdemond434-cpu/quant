param(
    [int]$Port = 8080,
    [string]$HostAddress = "127.0.0.1"
)

$Repo = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

Set-Location -LiteralPath $Repo
Write-Host "ZENTECH -> http://127.0.0.1:$Port/zentech.html"
& $Python scripts\serve_dashboard.py --host $HostAddress --port $Port
