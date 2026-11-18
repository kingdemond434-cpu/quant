@echo off
rem Every process, its last run and whether it is healthy -- hourly, so the board is never
rem reasoning from a reading nobody refreshed. Writes desks/mt5/reports/process_health.json,
rem which build_zentech_state.py publishes as desk_state.processes.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ProcessHealth.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\process_health.py" >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
rem Per-region deep forest production and the fault queue the box could not heal, on the same
rem hourly clock; the box-state push carries both off the box. Neither changes the exit code.
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\deep_forest_regions.py" >>"%LOG%" 2>&1
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\fault_queue.py" >>"%LOG%" 2>&1
exit /b %RC%
