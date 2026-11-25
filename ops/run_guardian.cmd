@echo off
rem THE BOX GUARDIAN (2026-11-25): every 15 minutes as SYSTEM, independent of the hourly cycle.
rem 1. ops\alert_feed.py reads every box page back off the ntfy topic into
rem    desks\mt5\reports\alerts\CLAUDE_ALERT_FEED.jsonl (box alerts go to Claude, not a phone).
rem 2. desk_self_heal --apply acts on desks\mt5\reports\process_health.json: bounded End+Run of
rem    faulted non-money tasks, pages for everything else. It never touches the money path.
rem    It first runs box_headroom (disk/RAM/CPU/terminals/quotas, invariants I6/I7): logs rolled
rem    and compressed, derived caches cleared past the 75% line; evidence is never deleted.
rem    And last, box_pass: the hourly pass on the box (principal 11-25 03:11Z), read-only ->
rem    desks\mt5\reports\PASS_FINDINGS.json.
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-Guardian.log"
set "PY=C:\Program Files\Python314\python.exe"
"%PY%" -u "C:\opt\quant\ops\alert_feed.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\desks\mt5\research\run_desk_self_heal.py" --apply >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
