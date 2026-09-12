@echo off
rem Deterministic row -> candidate conversion, whole corpus, every hour.
rem
rem No seat, no network, no per-row cost: it resolves rows against the desk's own universe
rem registry and executable family set and emits STRUCTURED_HYPOTHESIS rows the compiler already
rem accepts. Measured 2026-09-11 on 60,000 rows: 3 converted, 59,986 left for the model -- which
rem is the honest yield of the corpus as it stands, not a fault of the converter. It runs over
rem EVERYTHING hourly because it is free and because the yield rises the moment the miners start
rem emitting structure instead of post titles.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-LocalConvert.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\local_converter.py" --limit 0 >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
