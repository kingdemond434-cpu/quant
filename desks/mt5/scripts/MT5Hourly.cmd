@echo off
rem THE ONLY LAUNCHER OF research\hourly_cycle.py, and therefore of the whole daily chain.
rem Until 2026-09-05 this file cd'd into the RETIRED laptop's checkout and ran its Python
rem (C:\Users\dell\...), neither of which exists on Contabo -- hourly_cycle.py itself had
rem already been corrected to sys.executable, this launcher had not. Same convention as every
rem other box task (install_*.ps1): the desk root under C:\opt\quant and the `py -3` launcher.
cd /d C:\opt\quant\desks\mt5
:loop
py -3 research\hourly_cycle.py
timeout /t 3540 /nobreak >nul
goto loop
