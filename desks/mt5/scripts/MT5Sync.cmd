@echo off
rem MT5Sync.cmd - push the MT5 desk to the VPS brains at least hourly.
rem Loop every 60s: if the last full sync is older than 1h, sync now.
cd /d C:\Users\dell\mt5-research
:loop
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\dell\mt5-research\scripts\sync_to_vps.ps1"
timeout /t 60 /nobreak >nul
goto loop