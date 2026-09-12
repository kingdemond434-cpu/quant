@echo off
rem Re-earn the gold entry hours. Idempotent on the executable spec, so running it daily adds
rem nothing once the 48 cells are in the docket -- it exists so a REBUILT docket never silently
rem loses them, which is how the original sweep's result was lost in the first place.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-GoldHourSweep.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\gold_hour_sweep.py" --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
