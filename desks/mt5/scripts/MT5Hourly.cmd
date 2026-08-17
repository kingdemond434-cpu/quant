@echo off
cd /d C:\Users\dell\mt5-research
:loop
"C:\Users\dell\AppData\Local\Programs\Python\Python312\python.exe" research\hourly_cycle.py
timeout /t 3540 /nobreak >nul
goto loop