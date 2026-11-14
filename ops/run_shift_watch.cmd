@echo off
rem HAS THE MEASURING STICK MOVED? Wires libs/research/dist_shift.py, which was built 2026-07-29
rem and measured DECORATIVE on 2026-09-12 -- nothing outside its own module had ever called it.
rem
rem It flags a LIVE sleeve whose symbol's return distribution has moved away from the one its
rem thresholds were calibrated in. One-way by design: flags for re-validation and recommends a
rem downward confidence haircut, never promotes and never auto-demotes.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ShiftWatch.log"
rem THE EXIT IS THE STEP'S, NOT A CONSTANT (2026-10-14). This file ended `exit /b 0`, so the scheduler
rem read success whatever the step returned and process_health could never report it FAILING.
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\shift_watch.py" --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
