@echo off
rem THE PAPER CLOCK ON THE BOX (2026-11-25). seed_miners' research_feeds (NBER, Fed, BIS, ECB,
rem BoC, RBA ... see desks\mt5\side_channels\research_feeds.json), arxiv_qfin (all nine q-fin
rem categories, head + backfill) and bis_speeches had one dedicated clock: the Hetzner VPS timer
rem quant-seed-miners.timer (ops/crontab.manifest), retired for this desk. On the box they only
rem ran as a rotating beat of the heavy-plan scout_swarm leg. This runs JUST those three, cheap
rem (a few dozen RSS/Atom/API GETs, 1 s spacing, 3 s for arXiv), every 6 hours. RESEARCH ONLY.
rem global_journals (2026-11-25) adds the non-English readers: OAI-PMH and official APIs, at
rem most ~100 GETs a pass. Budget 2000 s: launches stop at 75%% of it, inside the 40-minute wall.
setlocal
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\Quant-ResearchFeeds.log"
set "PY=C:\Program Files\Python314\python.exe"
cd /d C:\opt\quant
>>"%LOG%" echo === Quant-ResearchFeeds start %DATE% %TIME%
"%PY%" -u desks\mt5\side_channels\seed_miners.py --only research_feeds,arxiv_qfin,bis_speeches,global_journals --budget-s 2000 >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo === Quant-ResearchFeeds end rc=%RC% %DATE% %TIME%
exit /b %RC%
