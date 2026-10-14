@echo off
rem CATCH STALENESS BEFORE A HUMAN DOES. Every 15 minutes: refresh the health reading, then act
rem on it. Both in one wrapper and in that order, because a watchdog acting on a stale board
rem restarts things that are already fine -- never_stale refuses a reading older than 90 minutes
rem for exactly that reason, and refreshing first means it never has to.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-NeverStale.log"
set "PY=C:\Program Files\Python314\python.exe"
rem THE EXIT IS THE STEP'S, NOT A CONSTANT (2026-10-14). This file ended `exit /b 0`, so the scheduler
rem read success whatever its steps returned and process_health could never report it FAILING.
set "WORST=0"
"%PY%" -u "C:\opt\quant\ops\process_health.py" >>"%LOG%" 2>&1
if not "%ERRORLEVEL%"=="0" if "%WORST%"=="0" set "WORST=%ERRORLEVEL%"
"%PY%" -u "C:\opt\quant\ops\never_stale.py" --apply >>"%LOG%" 2>&1
if not "%ERRORLEVEL%"=="0" if "%WORST%"=="0" set "WORST=%ERRORLEVEL%"
exit /b %WORST%
