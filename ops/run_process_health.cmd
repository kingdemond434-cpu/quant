@echo off
rem Every process, its last run and whether it is healthy -- hourly, so the board is never
rem reasoning from a reading nobody refreshed. Writes desks/mt5/reports/process_health.json,
rem which build_zentech_state.py publishes as desk_state.processes.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ProcessHealth.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\process_health.py" >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
rem Did each account (fusion, e8, ftmo) fill today? Read-only over the box's ledgers; writes
rem desks/mt5/reports/DAILY_FILLS.json and alarms a closed market day with no entry. It rides this
rem half-hourly clock on purpose (no new task) and never changes this task's result.
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\daily_fills.py" >>"%LOG%" 2>&1
exit /b %RC%
