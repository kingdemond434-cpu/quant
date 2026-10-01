@echo off
rem ===================================================================================
rem MT5-DeepenUniverse: take every bar Fusion will serve for a chart the desk already has.
rem
rem WHY A SEPARATE ORGAN FROM run_universe.cmd. `download_all_symbols` is MISSING-SERIES
rem incremental -- it skips any (symbol, timeframe) whose parquet exists -- so the depth of
rem every series on this box is frozen at whatever the producer that first created it asked
rem for, and `refresh_tail` only ever appends the NEW end. Nothing in the desk had ever
rem widened a file that already existed. Measured 2026-09-24: XAUUSD, the only symbol the
rem scalp lane trades, held 20,441 M5 bars while the terminal was serving 99,999.
rem
rem PYTHONPATH IS WHAT MAKES `mt5desk` IMPORTABLE. Python puts the SCRIPT'S directory on
rem sys.path, never the working directory, so neither a bare invocation nor a `cd` into
rem desks\mt5 is enough -- see the same note in run_universe.cmd, which was failing with
rem ModuleNotFoundError on every run for an unknown number of days.
rem
rem THE BUDGET IS THE POINT, NOT A SAFETY MARGIN. This shares one terminal with the gateway,
rem the tick recorder and the hourly research cycle. It stops on its own budget and stands
rem down entirely inside the gold placement windows (03:40-04:20, 09:45-10:15, 13:45-14:15
rem UTC), and its cursor checkpoints every five symbols so a stop costs the next pass nothing.
rem
rem THE SINGLETON CHECK IS NOT TIDINESS, IT IS A SILENT NO-OP THIS TASK HAS ALREADY HAD.
rem `schtasks /End` kills the cmd.exe wrapper and NOT the python child, so a stopped run leaves
rem an orphan. That orphan holds "%LOG%" open for append, the next run's `>>` cannot open it,
rem cmd aborts before the first line -- and the task reports LAST RESULT 0. Measured
rem 2026-09-24 22:58: a run that did nothing at all, logged nothing at all, and read as success.
rem The check runs BEFORE any redirection for exactly that reason: once the log is blocked,
rem nothing written through it can report the problem.
rem ===================================================================================

set "PYTHONPATH=C:\opt\quant\desks\mt5;C:\opt\quant"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-DeepenUniverse.log"
set "STANDDOWN=C:\opt\quant\desks\mt5\logs\MT5-DeepenUniverse.standdown.log"

rem MATCH THE .py, NEVER THE BARE NAME. The first version of this line looked for
rem "deepen_universe" and stood down on EVERY run, forever -- because the cmd.exe wrapper
rem executing THIS FILE has "run_deepen_universe.cmd" on its own command line and matched.
rem A guard against a silent no-op that is itself a silent no-op leaves no trace at all except
rem a stand-down log nobody reads; it was caught in one pass only because the stand-down file
rem was new and therefore worth opening. The ".py" suffix is what tells the worker from its
rem launcher.
rem psutil, never Get-CimInstance: CIM has hung on this box and wmic is absent (CLAUDE.md).
"C:\Program Files\Python314\python.exe" -c "import os,sys,psutil; me=os.getpid(); sys.exit(1 if any(p.pid!=me and 'deepen_universe.py' in ' '.join(p.info.get('cmdline') or []) for p in psutil.process_iter(['cmdline'])) else 0)"
if errorlevel 1 (
    echo %DATE% %TIME% a deepen pass is already running; not starting a second>>"%STANDDOWN%"
    exit /b 0
)

echo(>>"%LOG%"
echo ==== run_deepen_universe %DATE% %TIME% ====>>"%LOG%"

"C:\Program Files\Python314\python.exe" -u -W ignore ^
  "C:\opt\quant\desks\mt5\research\deepen_universe.py" --budget-s 1500 >>"%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo deepen_universe rc=%RC%>>"%LOG%"
exit /b %RC%
