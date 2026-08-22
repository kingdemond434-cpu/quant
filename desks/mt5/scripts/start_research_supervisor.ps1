$ErrorActionPreference = "Stop"
$DeskRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $DeskRoot "..\..")).Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) { throw "repo Python missing: $VenvPython" }
$Python = (& $VenvPython -c "import sys; print(sys._base_executable)").Trim()
$Script = Join-Path $DeskRoot "research\research_supervisor.py"
$PidFile = Join-Path $DeskRoot "logs\research_supervisor.pid"
if (Test-Path $PidFile) {
    $oldPid = 0
    [void][int]::TryParse((Get-Content $PidFile -Raw).Trim(), [ref]$oldPid)
    if ($oldPid -gt 0 -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { exit 0 }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}
Start-Process -FilePath $Python -ArgumentList ('"{0}"' -f $Script) `
    -WorkingDirectory $DeskRoot -WindowStyle Hidden
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 250
    if (Test-Path $PidFile) { exit 0 }
}
throw "research supervisor did not publish its PID"
