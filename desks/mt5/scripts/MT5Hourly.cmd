@echo off
rem THE ONLY LAUNCHER OF research\hourly_cycle.py, and therefore of the whole daily chain.
rem Until 2026-09-05 this file cd'd into the RETIRED laptop's checkout and ran its Python
rem (C:\Users\dell\...), neither of which exists on Contabo -- hourly_cycle.py itself had
rem already been corrected to sys.executable, this launcher had not. Same convention as every
rem other box task (install_*.ps1): the desk root under C:\opt\quant and the `py -3` launcher.
rem
rem THE SLEEP IS TO THE HOUR BOUNDARY, NOT A FIXED 3540 SECONDS AFTER THE PASS FINISHES, and
rem that distinction became load-bearing the day the cycle gained real work. `timeout /t 3540`
rem measures from the moment the cycle RETURNS, so the period is (pass duration + 59 minutes):
rem a cycle that now drains the deepening queue for up to 40 minutes, mines, heals clocks and
rem writes its marker turns an "hourly" loop into one that fires every hour and three quarters
rem and slides a little further every pass. Nothing reports that -- the marker is written on
rem every pass, so the cycle looks healthy while its cadence quietly halves.
rem
rem Sleeping to the top of the next hour makes the period what the name says, whatever the pass
rem costs: a fast pass waits longer, a slow one waits less, and a pass that overruns the hour
rem starts the next one immediately (MT5-StallWatch's STACKED heal keeps the oldest parent, so
rem an overlap costs a kill rather than two racing writers). The 60-second floor stops a
rem pathological zero-cost pass from spinning.
cd /d C:\opt\quant\desks\mt5
:loop
py -3 research\hourly_cycle.py
py -3 -c "import time; time.sleep(max(60.0, 3600.0 - (time.time() %% 3600.0)))"
goto loop
