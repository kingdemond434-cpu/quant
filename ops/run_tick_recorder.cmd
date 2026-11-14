@echo off
rem MT5-TickRecorder: the resident bronze tick recorder (desks/mt5/recorders/tick_recorder.py).
rem
rem WHY A RUNNER (2026-10-14). The task used to start `py -3 -m recorders.tick_recorder` with no
rem log, so when it returned 1 at 2026-10-12 19:56 box time nothing on the box said why, and the
rem cause could only be inferred. Every line it prints now lands in MT5-TickRecorder.log.
rem
rem THE EXIT IS THE RECORDER'S. Exit 4 = started in Windows Session 0 (re-register Interactive);
rem 5 = HUNG (no cycle in 10 min); 6 = STALLED (no new tick in 2 h while connected);
rem 1 = a traceback or a kill. The resident loop never returns on its own, so any exit at all is
rem a finding, and the task's repetition trigger relaunches it within ten minutes.
rem
rem The log is rolled at ~20 MB to one .1 generation: a resident loop prints a line a minute.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-TickRecorder.log"
if not exist "C:\opt\quant\desks\mt5\logs" mkdir "C:\opt\quant\desks\mt5\logs"
if exist "%LOG%" for %%F in ("%LOG%") do if %%~zF GTR 20000000 move /y "%LOG%" "%LOG%.1" >nul
cd /d "C:\opt\quant\desks\mt5"
echo %DATE% %TIME% MT5-TickRecorder start>>"%LOG%"
"C:\Program Files\Python314\python.exe" -u -m recorders.tick_recorder %* >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
echo %DATE% %TIME% MT5-TickRecorder exit rc=%RC%>>"%LOG%"
exit /b %RC%
