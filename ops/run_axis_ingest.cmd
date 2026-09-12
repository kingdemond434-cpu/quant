@echo off
rem Turn reachable axes into dated series the families can condition on.
rem
rem EVERY AXIS, EVERY PASS (2026-09-12, principal: "no make it ingest all there always bro").
rem This used to pass `--axis cot`, which runs exactly ONE of the four ingesters and then writes
rem the SHARED report -- so three axes never refreshed on the clock, and AXIS_INGEST.json carried
rem whichever axis happened to run last. Measured that day it held FRED's result (0 series, 7
rem failed) while COT had just ingested 4,060 rows across 22 MT5 symbols and BIS 464,803 across
rem 33. A board showing one lane's worst pass and hiding three healthy ones is what teaches an
rem operator to stop reading it.
rem
rem axis_ingest_all drives axis_ingest.INGESTERS, so a new axis added there is picked up here for
rem free, each axis writes its own file, and one publisher's outage is recorded as UNMEASURED
rem without stopping the other three. FRED currently times out and resets from this box's IP --
rem that is a fact about one publisher's edge network, not about the axis lane.
rem
rem SSL_CERT_FILE is not optional: without a CA store every HTTPS fetch fails verification and
rem reads as an unreachable source. That misdiagnosis cost seven of eleven sources once already.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-AxisIngest.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\research\axis_ingest_all.py" --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
