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
set "PYARGS="
rem The trading box's production interpreter is first. The repository venv can be a launcher
rem into a retired Python during migrations; measured 2026-09-28 it left cmd.exe alive with no
rem Python child and no log output while the direct 3.14 interpreter connected to Fusion.
set "PYTHON=C:\Program Files\Python314\python.exe"
if not exist "%PYTHON%" set "PYTHON=C:\opt\quant\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=py"& set "PYARGS=-3"

echo(>>"%LOG%"
echo ==== run_universe %DATE% %TIME% ====>>"%LOG%"

rem FIRST refresh every existing chart. Measured 2026-09-30, this task returned 0 hourly while
rem forward clocks were blocked because existing M5/M15/M30/H1 files had not moved for 13+ hours.
rem Missing-series hydration and existing-series freshness are separate jobs; both belong to the
rem one interactive task guaranteed to own a logged-in Fusion terminal.
"%PYTHON%" %PYARGS% -u -W ignore "C:\opt\quant\desks\mt5\scripts\refresh_tail.py" >>"%LOG%" 2>&1
set RCR=%ERRORLEVEL%
echo refresh_tail rc=%RCR%>>"%LOG%"

rem download_all_symbols is missing-series incremental: after the first fill it requests only
rem new symbols/timeframes. expand_universe re-downloaded every existing series before reaching
rem H4, so an hourly execution limit could leave H4 permanently at zero while repeatedly paying
rem for M1..H1.
rem Unbuffered output is operational evidence: a four-hour recovery must expose its current cell
rem while it runs, not publish thousands of verdict lines only after the process exits.
"%PYTHON%" %PYARGS% -u -W ignore "C:\opt\quant\desks\mt5\scripts\download_all_symbols.py" >>"%LOG%" 2>&1
set RC1=%ERRORLEVEL%
echo download_all_symbols rc=%RC1%>>"%LOG%"

rem USDX IS BUILT, NOT DOWNLOADED: Fusion does not quote the dollar index the miners and packs
rem name as a factor. synthetic_usdx writes it from the six ICE legs once all six are on disk;
rem its exit code never fails the pass (a missing leg is reported, not an error).
"%PYTHON%" %PYARGS% -u -W ignore "C:\opt\quant\desks\mt5\research\synthetic_usdx.py" >>"%LOG%" 2>&1

rem THE REGISTRY REPAIR RUNS WHETHER OR NOT THE EXPANDER SUCCEEDED. It is the step that
rem reconciles the registry with what is actually on disk, so a partial expansion is exactly
rem when it is most worth running; chaining it behind `&&` meant it had never run at all.
"%PYTHON%" %PYARGS% "C:\opt\quant\scripts\repair_universe_registry.py" >>"%LOG%" 2>&1
set RC2=%ERRORLEVEL%
echo repair_universe_registry rc=%RC2%>>"%LOG%"

rem This is the interactive TRADING BOX collector, not the terminal-less VPS daily cycle.
rem refresh_tail rc=2 means no authenticated terminal and therefore no fresh broker bars.
rem Reporting a zero task result after that was the false-green state that let forward clocks
rem age into BLOCKED_NO_BARS while the hourly task appeared healthy.
if not "%RCR%"=="0" exit /b %RCR%
if not "%RC1%"=="0" exit /b %RC1%
exit /b %RC2%
