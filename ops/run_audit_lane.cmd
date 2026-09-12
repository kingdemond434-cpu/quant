@echo off
rem THE AUDIT LANE, ON THE BOX THAT HAS THE SEAT (2026-09-12).
rem
rem kimi_hunter, the deepseek cycle and the cold audits are all scheduled as systemd timers on the
rem VPS. Measured today: the VPS checkout is behind and unreachable, while the TRADING BOX holds a
rem working OpenRouter seat making 446 free-tier calls a day. So the desk had a key with no organs
rem on one box and organs with no reachable box on the other, and the whole audit lane produced
rem nothing anywhere: kimi_hunt, the kimi/deepseek donation dirs, hypothesis_queue, code_audit,
rem deep_audit, free_research and the panel log were ALL absent.
rem
rem Free tier is forced, so this costs nothing however often it runs.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "QUANT_FREE_TIER=1"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-AuditLane.log"
set "PY=C:\Program Files\Python314\python.exe"
"%PY%" -u "C:\opt\quant\desks\mt5\research\audit_intake.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\scripts\kimi_hunter.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\scripts\run_deepseek_cycle.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\scripts\hypothesis_generator.py" >>"%LOG%" 2>&1
exit /b 0
