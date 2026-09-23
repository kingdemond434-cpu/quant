@echo off
rem SAME-DAY CAPTURE COMPLETENESS. Runs beside the recorder, not on a daily review clock.
rem
rem The point is the window: MT5's copy_ticks_range serves what the broker still holds, so a gap
rem found within hours is often re-pullable and a gap found next month never is. Three short days
rem sat unreported in the five trading days before this was written -- every liveness reading
rem green, `gaps: 0`, and a third of the symbols simply never written.
rem
rem Exit code 1 means a short day was found. That is deliberate: MT5-NeverStale reads the
rem artifact, and a monitor whose failure is invisible to the watchdog is a monitor nobody reads.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "MOAT_ROOT=C:\moat"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-MoatCapture.log"
"C:\Program Files\Python314\python.exe" -u "C:\opt\quant\desks\mt5\moat\capture_watch.py" >>"%LOG%" 2>&1
exit /b 0
