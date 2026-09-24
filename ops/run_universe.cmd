@echo off
rem ===================================================================================
rem MT5-Universe: fill every missing broker chart, then repair the registry.
rem
rem WHY THIS IS A FILE AND NOT AN INLINE TASK ARGUMENT. The task used to carry the whole
rem pipeline as one quoted cmd.exe argument, and it had been dying on every run with
rem
rem     ModuleNotFoundError: No module named 'mt5desk'
rem
rem because Python puts the SCRIPT'S directory on sys.path, never the working directory --
rem so neither the bare invocation nor a `cd` into desks\mt5 ever made `mt5desk` importable.
rem PYTHONPATH is what actually fixes it, and setting PYTHONPATH inside a nested-quoted
rem scheduled-task argument is exactly the kind of thing that silently does not take.
rem In a file the quoting is unambiguous and the same line can be run by hand to check it.
rem
rem Measured 2026-09-11: the task had result 1 on every run, so the universe expander --
rem which is what keeps the bar files the whole hypothesis lane reads current -- had not
rem completed in an unknown number of days.
rem ===================================================================================

set "PYTHONPATH=C:\opt\quant\desks\mt5;C:\opt\quant"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-Universe.log"

echo(>>"%LOG%"
echo ==== run_universe %DATE% %TIME% ====>>"%LOG%"

rem download_all_symbols is missing-series incremental: after the first fill it requests only
rem new symbols/timeframes. expand_universe re-downloaded every existing series before reaching
rem H4, so an hourly execution limit could leave H4 permanently at zero while repeatedly paying
rem for M1..H1. Existing files are refreshed by refresh_tail in the hourly research cycle.
py -3 -W ignore "C:\opt\quant\desks\mt5\scripts\download_all_symbols.py" >>"%LOG%" 2>&1
set RC1=%ERRORLEVEL%
echo download_all_symbols rc=%RC1%>>"%LOG%"

rem THE REGISTRY REPAIR RUNS WHETHER OR NOT THE EXPANDER SUCCEEDED. It is the step that
rem reconciles the registry with what is actually on disk, so a partial expansion is exactly
rem when it is most worth running; chaining it behind `&&` meant it had never run at all.
py -3 "C:\opt\quant\scripts\repair_universe_registry.py" >>"%LOG%" 2>&1
set RC2=%ERRORLEVEL%
echo repair_universe_registry rc=%RC2%>>"%LOG%"

if not "%RC1%"=="0" exit /b %RC1%
exit /b %RC2%
