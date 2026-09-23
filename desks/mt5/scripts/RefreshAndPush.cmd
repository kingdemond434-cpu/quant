@echo off
rem Refresh MT5 universe tails then push desk to VPS (runs every 30 min via Task Scheduler)
cd /d C:\Users\dell\mt5-research
"C:\Users\dell\AppData\Local\Programs\Python\Python312\python.exe" scripts\refresh_tail.py >> data\refresh_tail.log 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\dell\mt5-research\scripts\sync_to_vps.ps1"
