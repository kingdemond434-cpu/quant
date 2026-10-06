@echo off
rem THE LAUNCHER FOR MT5-Gauntlet, and the reason it exists.
rem
rem `desks\mt5\scripts\external_gauntlet.py` is SEALED. Its `_worker_count()`, shard protocol and
rem `_measured_budget_mb()` already honour GAUNTLET_WORKERS, GAUNTLET_MEMORY_BUDGET_MB,
rem GAUNTLET_HEADROOM_CAP_MB and GAUNTLET_PER_WORKER_MB from the ENVIRONMENT. The launcher gives
rem its exposed fail-closed shard protocol the measured GAUNTLET_SHARDS count, so both the build
rem and cell-local gates use the box without changing a statistical rule. Until this file existed
rem there was
rem nowhere to set them: MT5-Gauntlet is one of the five research tasks `box_tasks.manifest`
rem records as having NO installer anywhere in this repository, so it ran the bare script with
rem whatever environment the scheduler handed it, which was none.
rem
rem `research\judging_throughput.py` measures this box every hour -- free cores, free physical
rem memory, free COMMIT, whether the live terminal is on the machine -- and writes the decision to
rem data\judging_throughput.env.json. This launcher reads that file and exports it. The decision is
rem floored at what the sealed file would choose unaided, so this can never throttle the judge; the
rem worst it can do is change nothing.
rem
rem A MISSING OR UNREADABLE ENV FILE CHANGES NOTHING. No variable is exported, the sealed file
rem derives its own worker count exactly as before, and the sweep runs. An absent measurement must
rem never be able to stop the judge.
cd /d C:\opt\quant\desks\mt5
for /f "usebackq delims=" %%L in (`py -3 -c "import json,pathlib;d=json.loads(pathlib.Path('data/judging_throughput.env.json').read_text('utf-8')).get('env',{});print('\n'.join(f'{k}={v}' for k,v in d.items()))" 2^>nul`) do set "%%L"
if exist C:\opt\quant-research-runtime\.venv\Scripts\python.exe (
  C:\opt\quant-research-runtime\.venv\Scripts\python.exe -u scripts\run_sharded_gauntlet.py %*
) else (
  py -3 -u scripts\run_sharded_gauntlet.py %*
)
