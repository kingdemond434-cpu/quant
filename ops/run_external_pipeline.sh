#!/bin/bash
# STAGES 2-3 OF THE SAME-DAY PIPELINE (RESEARCH §6d), chained so a discovery mined today is
# certified today: external hypotheses -> stage-A backtest -> full ten-gate gauntlet -> canon.
# Before 2026-08-26 both stages ran only when a human typed them; today's 15-pass sweep was a
# manual run, and tomorrow's discoveries would have sat unbacktested -- the exact waiting room
# the law forbids.
set -u
cd /home/quant/quant-platform
# SEALED AGAINST MID-RUN REWRITE (2026-08-26). bash reads a script INCREMENTALLY by byte
# offset; a commit that changes this file's LENGTH while it is running resumes execution inside
# a line. Measured on 63680c05 (ops/run_frontier_rotation.sh): comment text ran as a command,
# then a dangling `fi`, then the script RE-RAN ITSELF FROM THE TOP. Only the exit INSIDE the
# group ends the process before bash reads another byte. Do not unwrap; add nothing after `}`.
{
PY=.venv/bin/python
LOGF=data/cro_ai_logs/external_pipeline_gauntlet.log
export QUANT_PIPELINE_STARTED_AT="$(date -u +%FT%TZ)"

echo "[$(date -u +%FT%TZ)] stage 2: external backtest"
$PY desks/mt5/side_channels/run_external_backtest.py || echo "stage 2 FAILED (rc=$?)"

# STAGE 2b: the zero-hardcode search. It runs BEFORE the gauntlet so its diverse candidates are
# judged by the same ten gates as everything else -- and it carries its own trial count so the
# deflation is honest about how wide the search was.
# STAGE 2a: what did the miners and the MOAT point at this week? Mining supplies ATTENTION,
# not hypotheses -- 740 discovery files existed and none had ever reached the ten gates because a
# web artefact is not a (symbol, family, params). This turns them into a ranked search target
# list, hourly, and the moat's own tick tape weighs heaviest because nobody else has it.
# STAGE 1: precompute every number an LLM organ would otherwise count for itself. Python
# counts; the model judges. This runs first so anything downstream -- including the LLM organs on
# their own cadences -- reads current facts rather than deriving them.
echo "[$(date -u +%FT%TZ)] stage 1: research facts pack"
$PY scripts/build_research_facts.py || echo "facts pack FAILED (rc=$?) -- continuing"

echo "[$(date -u +%FT%TZ)] stage 2a: mined ground (miners + moat -> search targets)"
$PY desks/mt5/research/mined_ground.py || echo "mined ground FAILED (rc=$?) -- continuing"

# Heavy discovery belongs on the MT5 desk box. Measured 2026-08-26: running edge_search here
# OOM-killed this service after the 28-minute external screen, so neither search output reached
# merge or the gauntlet. The desk box has the same Fusion universe and ~8GB RAM; execute BOTH the
# family-free search and the named orthogonal falsification sweep there, then pull their artifacts
# into the one merge below. Discovery remains hourly; only the compute location changes.
echo "[$(date -u +%FT%TZ)] stage 2b: desk-box frontier search (family-free + orthogonal)"
scp -q desks/mt5/data/hypotheses/mined_targets.json \
    contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/mined_targets.json' 2>/dev/null || true

# These are independent discovery methods. Running them behind `A && B` made an OOM in the
# family-free search suppress the much cheaper orthogonal sweep. Pull an artifact only when its
# own producer succeeds; merge_hypotheses also rejects any artifact older than this pipeline run.
if ssh -o ConnectTimeout=20 contabo-mt5 \
     "cd C:\opt\quant\desks\mt5 && py -3 -W ignore research\orthogonal_sweep.py" \
     >> "$LOGF" 2>&1; then
  scp -q contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/orthogonal_candidates.json' \
      desks/mt5/data/hypotheses/orthogonal_candidates.json 2>/dev/null \
    && echo "orthogonal frontier artifact pulled" \
    || echo "orthogonal frontier pull FAILED"
else
  echo "orthogonal frontier FAILED on the desk box -- see $LOGF"
fi

if ssh -o ConnectTimeout=20 contabo-mt5 \
     "cd C:\opt\quant\desks\mt5 && py -3 -W ignore research\edge_search.py" \
     >> "$LOGF" 2>&1; then
  scp -q contabo-mt5:'C:/opt/quant/desks/mt5/data/hypotheses/edge_search_results.json' \
      desks/mt5/data/hypotheses/edge_search_results.json 2>/dev/null \
    && echo "family-free frontier artifact pulled" \
    || echo "family-free frontier pull FAILED"
else
  echo "family-free frontier FAILED on the desk box -- see $LOGF"
fi

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

exit $?
}
