@echo off
rem THE DAILY CEO LOOP. The frontier organ scouts; this ranks what it found into proposals with an
rem experiment and a falsifier each; the operator decides and implements. 05:10 UTC, after the
rem overnight sweep has finished and before the Asia gold window at 07:00 broker time, so a
rem decision taken today can be in the docket the same day.
rem
rem The breadth sweep runs FIRST, so any gap that became unblocked overnight is already cells by
rem the time the docket is written and the proposal reads "done" instead of "todo".
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-CEODocket.log"
set "PY=C:\Program Files\Python314\python.exe"
"%PY%" -u "C:\opt\quant\desks\mt5\research\breadth_sweep.py" --apply >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\desks\mt5\research\frontier_ceo.py" --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
