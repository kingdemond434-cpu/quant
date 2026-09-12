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
rem DEEPSEEK RUNS ON A DIFFERENT FREE FAMILY, BECAUSE DEEPSEEK IS NOT ONE (2026-09-12).
rem
rem Measured against this account's own catalogue: 445 models served, 19 of them free, and NOT
rem ONE is a DeepSeek, Kimi, Qwen, Moonshot, GLM or MiniMax id. That is why deepseek-r1:free and
rem kimi-k2:free both return 404 and kimi's chain walks past three dead entries to nemotron. The
rem free tier here is nvidia/nemotron, google/gemma, inclusionai/ling, poolside, cohere, nex-agi.
rem
rem The flywheel's value is a genuinely DIFFERENT PRIOR from Claude's, not the DeepSeek brand, so
rem gemma is a real substitute for its purpose. It is also deliberately a different vendor from
rem the nemotron kimi lands on: two seats agreeing because they are the same model is not
rem cross-family evidence, it is one opinion counted twice.
rem
rem Set EXPLICITLY here rather than defaulted in code: deepseek_cycle refuses to substitute a
rem model silently ("a silent substitution would corrupt the only measurement this flywheel
rem exists to produce"), and that refusal is right. This is configuration, on the record.
rem gemma free is RATE-LIMITED UPSTREAM (HTTP 429 from Google AI Studio on first call),
rem so bulk uses the vendor that is demonstrably answering -- 446 calls today without a
rem refusal -- at a DIFFERENT size from the ultra kimi lands on, so the two seats are not
rem the same model counted twice.
set "DEEPSEEK_BULK_MODEL=nvidia/nemotron-3-super-120b-a12b:free"
set "DEEPSEEK_DEEP_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free"
set "SSL_CERT_FILE=C:\Program Files\Python314\Lib\site-packages\certifi\cacert.pem"
set "LOG=C:\opt\quant\desks\mt5\logs\MT5-AuditLane.log"
set "PY=C:\Program Files\Python314\python.exe"
"%PY%" -u "C:\opt\quant\desks\mt5\research\audit_intake.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\scripts\kimi_hunter.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\scripts\run_deepseek_cycle.py" >>"%LOG%" 2>&1
"%PY%" -u "C:\opt\quant\scripts\hypothesis_generator.py" >>"%LOG%" 2>&1
rem THE RESEARCH TREE JOINS THE HOURLY LANE (F6, 2026-09-12), not the daily one. It reads
rem JSON and writes JSON -- the cost is negligible -- and a persistent tree only reaches
rem depth by being expanded, so its cadence IS its reach. A beam of 12 an hour grows the
rem tree a level a day; the same beam once a day would take a fortnight to ask a
rem cross-market question of a mechanism that certified this morning.
"%PY%" -u "C:\opt\quant\desks\mt5\research\research_tree.py" --apply >>"%LOG%" 2>&1
exit /b 0
