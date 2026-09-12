@echo off
rem CATCH STALENESS BEFORE A HUMAN DOES. Every 15 minutes: refresh the health reading, then act
rem on it. Both in one wrapper and in that order, because a watchdog acting on a stale board
rem restarts things that are already fine -- never_stale refuses a reading older than 90 minutes
rem for exactly that reason, and refreshing first means it never has to.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-NeverStale.log"
set "PY=C:\Program Files\Python314\python.exe"
"%PY%" -u "C:\opt\quant\ops\process_health.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\ops\never_stale.py" --apply >>"%LOG%" 2>&1
exit /b 0
