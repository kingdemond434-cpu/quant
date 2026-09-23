@echo off
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-ConvertSwarm.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\ops\convert_swarm.py" --per-lane 0 --budget-sec 2100 >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
