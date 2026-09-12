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
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-CostState.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\cost_surface.py" >>"%LOG%" 2>&1
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\carry_state.py" >>"%LOG%" 2>&1
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\cost_honesty.py" --apply >>"%LOG%" 2>&1
exit /b 0
