@echo off
rem Every process, its last run and whether it is healthy -- hourly, so the board is never
rem reasoning from a reading nobody refreshed. Writes desks/mt5/reports/process_health.json,
rem which build_zentech_state.py publishes as desk_state.processes.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ProcessHealth.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\process_health.py" >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
rem PASS WATCH (2026-11-18): the hourly pass's numeric checks, no LLM, flag only on change.
rem Reads the report just written plus release_identity and MERGE_PIPELINE; writes PASS_WATCH.json.
rem Its own failure never changes this task's exit code.
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\pass_watch.py" >>"%LOG%" 2>&1
exit /b %RC%
