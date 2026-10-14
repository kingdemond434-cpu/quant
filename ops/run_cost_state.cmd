@echo off
rem THE TWO COST PRODUCERS, finally on a clock (2026-09-12).
rem
rem check_enforcement_execution measured both MENTIONED: named in other files only as text, never
rem called, though each has a main() and each writes an artifact. They were built because the
rem desk's cost model is wrong in a stated way -- cost_surface: "spread is a symbol x HOUR state,
rem not one scalar per symbol"; carry_state: "grep -i swap engine.py returns ZERO hits". Unread,
rem they changed nothing.
rem
rem Daily, because both are distributional: a spread surface and a financing table move on the
rem scale of a session calendar, not of an hour, and rebuilding them hourly would spend the box's
rem parquet IO to re-derive the same numbers.
rem
rem THE EXIT IS THE WORST STEP'S, NOT A CONSTANT (2026-10-14). This file ended `exit /b 0`, so
rem the scheduler read success whatever the producers returned, while carry_state was never seen
rem published from the box and cost_surface's last stamp on origin was 2026-09-23. All three steps
rem still run (one failing must not starve the others); each stamps its own exit code into the
rem log as `MT5-CostState step=<name> rc=<n>`, which scripts/check_cost_state_fresh.py reads, and
rem the task returns the first non-zero code so LastTaskResult names a failure.
setlocal EnableDelayedExpansion
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-CostState.log"
set "PY=C:\Program Files\Python314\python.exe"
set "WORST=0"
for %%S in (cost_surface carry_state cost_honesty) do (
    set "ARGS="
    if "%%S"=="cost_honesty" set "ARGS=--apply"
    "%PY%" -u "C:\opt\quant\desks\mt5\research\%%S.py" !ARGS! >>"%LOG%" 2>&1
    set "RC=!ERRORLEVEL!"
    >>"%LOG%" echo MT5-CostState step=%%S rc=!RC! at=!DATE! !TIME!
    if not "!RC!"=="0" if "!WORST!"=="0" set "WORST=!RC!"
)
exit /b %WORST%
