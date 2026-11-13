@echo off
rem THE SIDE-CHANNEL MINER SUITE ON THE BOX (2026-11-05).
rem
rem desks\mt5\side_channels\run_all_miners.py runs the 25 external discovery channels (aaii, cot,
rem central banks, sec_edgar, seasonality, weather, shipping, china, korea, ...). Each miner's
rem run_and_save writes its own seat under desks\mt5\data\intelligence\, which the miner compiler
rem reads. Its only callers were scripts on the Linux VPS chain (ops/run_daily_brain_chain.sh),
rem whose intel-ship stopped on 2026-11-03, so 19 seats went DEAD together in PRODUCER_YIELD on
rem 2026-11-05. This gives the suite its own seat on the box, so it runs 24/7 where the compiler is.
rem
rem RESEARCH ONLY: miners write discovery rows for the compiler and the judge, nothing else.
rem
rem One miner is killed after QUANT_MINER_TIMEOUT_S (180 s) so a hung channel never stalls the
rem rest; the suite exits 0 when it finished, whatever each channel returned, and the per-seat
rem counts land in latest_discoveries.json and PRODUCER_YIELD.
rem
rem CLEAR-ACCESS CHANNELS ONLY (Auditor HOLD on #773). The box runs only channels that use an
rem official API, open data or local computation: cot (CFTC), central_bank (central-bank RSS),
rem weather (Open-Meteo, NOAA, Drought Monitor), github (GitHub API), seasonality and
rem correlations (local), and sec_edgar when QUANT_EDGAR_UA is set. Every other channel, the web
rem scrapers and youtube among them, is reported SET_ASIDE by name in latest_discoveries.json.
rem The box never contacts YouTube.
setlocal
set "QUANT_MINERS_ALLOW=cot,central_bank,weather,github,seasonality,correlations,sec_edgar"
set "PYTHONPATH=C:\opt\quant;C:\opt\quant\desks\mt5"
set "LOG=C:\opt\quant\desks\mt5\logs\Quant-SideChannelMiners.log"
set "PY=C:\Program Files\Python314\python.exe"
cd /d C:\opt\quant
>>"%LOG%" echo === Quant-SideChannelMiners start %DATE% %TIME%
rem COT positioning first (2026-11-13): mt5desk.cot_refresh fetches only when the CFTC has
rem released a Tuesday the held parquets lack, so on most passes it sends no request at all.
rem It runs from desks\mt5 so `mt5desk` imports; its report is desks\mt5\reports\COT_REFRESH.json.
pushd desks\mt5
"%PY%" -u -m mt5desk.cot_refresh >>"%LOG%" 2>&1
popd
"%PY%" -u desks\mt5\side_channels\run_all_miners.py >>"%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo === Quant-SideChannelMiners end rc=%RC% %DATE% %TIME%
exit /b %RC%
