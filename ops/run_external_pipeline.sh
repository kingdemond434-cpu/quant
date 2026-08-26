#!/bin/bash
# STAGES 2-3 OF THE SAME-DAY PIPELINE (RESEARCH §6d), chained so a discovery mined today is
# certified today: external hypotheses -> stage-A backtest -> full ten-gate gauntlet -> canon.
# Before 2026-08-26 both stages ran only when a human typed them; today's 15-pass sweep was a
# manual run, and tomorrow's discoveries would have sat unbacktested -- the exact waiting room
# the law forbids.
set -u
cd /home/quant/quant-platform
PY=.venv/bin/python
LOGF=data/cro_ai_logs/external_pipeline_gauntlet.log

echo "[$(date -u +%FT%TZ)] stage 2: external backtest"
$PY desks/mt5/side_channels/run_external_backtest.py || echo "stage 2 FAILED (rc=$?)"

# STAGE 2b: the zero-hardcode search. It runs BEFORE the gauntlet so its diverse candidates are
# judged by the same ten gates as everything else -- and it carries its own trial count so the
# deflation is honest about how wide the search was.
echo "[$(date -u +%FT%TZ)] stage 2b: generic edge search (no families, diversity-selected)"
$PY desks/mt5/research/edge_search.py || echo "edge search FAILED (rc=$?) -- continuing"

# STAGE 2c: merge every producer into the ONE file the gauntlet reads. Without this the search
# and the sweep write files nothing consumes -- producers with no consumer, which is how the book
# stayed 95% one family while the searcher "ran nightly".
echo "[$(date -u +%FT%TZ)] stage 2c: merge hypothesis sources"
$PY desks/mt5/research/merge_hypotheses.py || echo "merge FAILED (rc=$?)"

# STAGE 3 RUNS ON THE DESK BOX, NOT HERE. Measured 2026-08-26: a 208-cell gauntlet (100 of them
# discovered edges with ~5,000 signals each) was OOM-killed on this 4GB box -- 25 OOM events in 90
# minutes -- while the desk box sat with 4.1GB free of 8GB and already holds the universe. Heavy
# compute follows the memory and the data; this box coordinates and keeps the canon. Running it
# here would silently truncate the gauntlet to whatever fits, which is worse than not running it:
# a partial gauntlet still writes verdicts.
echo "[$(date -u +%FT%TZ)] stage 3: ten-gate gauntlet (on the desk box)"
scp -q desks/mt5/data/hypotheses/external_survivors.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/external_survivors.json' 2>/dev/null
if ssh -o ConnectTimeout=20 contabo-mt5 \
     "cd C:\opt\quant\desks\mt5 && py -3 -W ignore scripts\external_gauntlet.py" \
     >> "$LOGF" 2>&1; then
  scp -q contabo-mt5:'C:/opt/quant/desks/mt5/reports/UNIVERSAL_SURVIVORS.json' \
      desks/mt5/reports/UNIVERSAL_SURVIVORS.json 2>/dev/null
  scp -q contabo-mt5:'C:/opt/quant/desks/mt5/reports/universal_gates_external.json' \
      desks/mt5/reports/universal_gates_external.json 2>/dev/null
  echo "gauntlet done on the desk box; certificates pulled back"
else
  echo "stage 3 FAILED on the desk box -- see $LOGF"
fi

# Stage 4: certificates -> canon copy -> desk box. The canon file is what the authority
# ratchet floors and what restores the authority file after a bad writer.
$PY - <<'PYEOF'
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, ".")
from libs.ops.canon_lease import hold
auth = Path("desks/mt5/reports/UNIVERSAL_SURVIVORS.json")
canon = Path("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json")
a = json.loads(auth.read_text("utf-8"))
c = json.loads(canon.read_text("utf-8")) if canon.exists() else {"survivors": {}}
if len(a.get("survivors", {})) >= len(c.get("survivors", {})):
    # UNDER LEASE. Two certifiers wrote this file tonight and the loser was whichever ran first;
    # the lease serialises them and fences a stalled writer out entirely.
    with hold("desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json", "external-pipeline") as tok:
        shutil.copyfile(auth, canon)
        print(f"canon updated under lease {str(tok)[:12]}: n={len(a['survivors'])}")
else:
    print(f"canon NOT updated: authority {len(a.get('survivors', {}))} < canon "
          f"{len(c['survivors'])} -- ratchet holds")
PYEOF

scp -q desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json' \
  && echo "canon synced to desk box" || echo "desk-box sync FAILED (will retry next run)"

# The hypothesis corpus lives on THIS box (stage 2 writes it here) but the dashboard state is
# built on the desk box, which is the only machine that can read the live account. Without this
# the funnel's first stage reads null -- "discovered" unmeasured -- while every later stage has
# a number, which reads as a broken pipeline rather than a missing file.
scp -q desks/mt5/data/hypotheses/external_backtest_results.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/external_backtest_results.json' \
  2>/dev/null && echo "hypothesis corpus synced" || echo "hypothesis sync skipped"
echo "[$(date -u +%FT%TZ)] external pipeline done"
