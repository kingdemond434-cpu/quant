@echo off
rem HUNT DATA AXES HOURLY, with the same cadence the strategy-claim miners get.
rem
rem The claim miners read 204,581 rows and convert to 125 distinct exposures; adding 74 aliases
rem moved that by ONE. The corpus is not the constraint -- the number of distinct things it can
rem SAY is, and everything it says is about price. An AXIS is an input the desk does not hold at
rem all, and six of the seven REACHABLE breadth gaps are blocked on one.
rem
rem It PROBES rather than assumes: a source is usable only when it was reached from this box.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-DataAxis.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\data_axis_miner.py" --probe --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
