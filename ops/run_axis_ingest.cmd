@echo off
rem Turn reachable axes into dated series the families can condition on. Daily: the COT prints
rem weekly and the macro series daily, so an hourly cadence would be re-fetching an unchanged file.
rem The annual archives are immutable once a year closes, so the backfill is paid once.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-AxisIngest.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\axis_ingest.py" --axis cot --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
