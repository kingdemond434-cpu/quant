@echo off
rem ===================================================================================
rem THE STANDING HEALERS, on a clock.
rem
rem Three separate organs silently shrank the book on 2026-09-11 and every status page read
rem healthy while they did it:
rem
rem   82 forward clocks  RETIRED_ORPHAN after the certificate registry oscillated
rem                      55->58->66->58->66->58 and the admission rule tightened
rem   21 live sleeves    demoted LIVE->STANDBY with NO reason recorded on any field
rem   n  forward clocks  IDENTITY_BROKEN when a family's code hash moved
rem
rem Each was found by a human noticing a number looked wrong, days after the fact. A fixer that
rem only runs when someone notices is not a fixer, it is a fire drill -- III.16: done means RUNS
rem on a schedule and leaves an artifact.
rem
rem REPORT-ONLY IS NOT AN OPTION HERE, and that is deliberate. These three restore REACHABILITY
rem and MEASUREMENT, never capital: a revived shadow clock holds no order authority, and a
rem restored LIVE row is priced by cap_by_heat and sized by the allocator exactly as before.
rem None of them can put on a position. What they undo is a verdict nobody recorded.
rem ===================================================================================

set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-Healers.log"
set "PY=C:\Program Files\Python314\python.exe"

echo(>>"%LOG%"
echo ==== healers %DATE% %TIME% ====>>"%LOG%"

"%PY%" -u "C:\opt\quant\desks\mt5\scripts\heal_silent_demotions.py" --apply >>"%LOG%" 2>&1
echo   silent_demotions rc=%ERRORLEVEL%>>"%LOG%"

"%PY%" -u "C:\opt\quant\desks\mt5\scripts\heal_orphaned_clocks.py" --apply >>"%LOG%" 2>&1
echo   orphaned_clocks rc=%ERRORLEVEL%>>"%LOG%"

"%PY%" -u "C:\opt\quant\desks\mt5\scripts\heal_identity_broken_clocks.py" --apply >>"%LOG%" 2>&1
echo   identity_broken_clocks rc=%ERRORLEVEL%>>"%LOG%"

exit /b 0
