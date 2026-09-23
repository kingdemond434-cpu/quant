@echo off
rem Publish the live account snapshot. A FILE, not an inline scheduled-task argument: the
rem inline form needs quotes around a python path that itself contains a space, nested inside
rem the quotes cmd.exe already owns, and it failed to start at all (0xC0000142) without ever
rem reaching the log. The same failure and the same fix as ops\run_universe.cmd.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-AccountState.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\publish_account_state.py" >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
