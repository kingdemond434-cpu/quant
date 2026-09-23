# RefreshAndPush.ps1 - runs as scheduled task
# Handles the MT5 refresh + VPS push from a proper non-interactive context

$ErrorActionPreference = "Continue"
$logDir = "C:\Users\dell\mt5-research\data"
$logFile = Join-Path $logDir "refresh_tail.log"

# 1. Refresh MT5 tails
& "C:\Users\dell\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\dell\mt5-research\scripts\refresh_tail.py" *>&1 | Out-File -FilePath $logFile -Encoding utf8

# 2. Force sync to VPS (bypass rate limit)
Remove-Item "C:\Users\dell\mt5-research\data\last_sync.json" -Force -ErrorAction SilentlyContinue
& powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\dell\mt5-research\scripts\sync_to_vps.ps1"
