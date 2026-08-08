#!/usr/bin/env bash
# SWEEP, THEN CYCLE -- and the ORDER is the whole point of the file existing.
#
# THE HAZARD THIS REMOVES. The operator was given two commands: start the sweep detached, then run
# the research cycle. Both are correct and running them back to back is WRONG, because the sweep
# takes roughly an hour and returns immediately when detached. The cycle would then consume the
# PREVIOUS run's artifacts -- or none at all -- and report a kill audit of stale cells, a portfolio
# admission of stale survivors, and a completion ledger measuring a cycle that never happened.
#
# Nothing would error. Every artifact would be present and internally consistent. The numbers would
# simply be about the wrong run, which is the most expensive kind of wrong this desk produces: it
# is indistinguishable from a real result until someone checks a timestamp.
#
# So the dependency becomes a script rather than an instruction. Instructions are followed by
# whoever read them most recently; a script is followed every time.
#
#   bash ops/run_sweep_then_cycle.sh            # sweep, wait, then the full cycle
#   bash ops/run_sweep_then_cycle.sh --cycle-only   # skip the sweep (it already finished)
#
# Safe to detach:
#   setsid nohup bash ops/run_sweep_then_cycle.sh > data/pipeline.log 2>&1 < /dev/null & disown
set -uo pipefail
cd "$(dirname "$0")/.."

LOG="data/pipeline_$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p data
SWEEP_REPORT="data/full_sweep.json"
CYCLE_ONLY="${1:-}"

PY=""
for _c in "$PWD/.venv/bin/python" .venv/bin/python python3; do
    if [ -x "$_c" ] || command -v "$_c" >/dev/null 2>&1; then PY="$_c"; break; fi
done
[ -n "$PY" ] || { echo "FATAL: no interpreter"; exit 1; }

{
echo "=== pipeline start $(date -u) ==="

if [ "$CYCLE_ONLY" != "--cycle-only" ]; then
    # THE PRE-RUN MTIME IS THE COMPLETION TEST. "Does full_sweep.json exist" is not a test -- it
    # exists from the LAST run. The sweep writes its report only at the end, so a report NEWER
    # than the moment we started is the one unambiguous signal that this run finished. Parsing the
    # log for a word would break the first time the wording changed.
    BEFORE=0
    [ -f "$SWEEP_REPORT" ] && BEFORE=$(stat -c %Y "$SWEEP_REPORT" 2>/dev/null || echo 0)
    echo "pre-run report mtime: $BEFORE"

    STUDY_FOREGROUND=1 bash ops/run_study_on_vps.sh full_sweep
    echo "=== sweep exited $? at $(date -u) ==="

    AFTER=0
    [ -f "$SWEEP_REPORT" ] && AFTER=$(stat -c %Y "$SWEEP_REPORT" 2>/dev/null || echo 0)
    if [ "$AFTER" -le "$BEFORE" ]; then
        echo "REFUSING TO RUN THE CYCLE: $SWEEP_REPORT was not rewritten, so the sweep did not"
        echo "  finish. Running the cycle now would audit the PREVIOUS run's kills and admit the"
        echo "  PREVIOUS run's survivors, and every number would look valid. Read the log above,"
        echo "  fix the cause, then re-run. --cycle-only skips this guard deliberately."
        exit 2
    fi
    echo "sweep report rewritten ($BEFORE -> $AFTER); artifacts are from THIS run"
fi

echo "=== research cycle $(date -u) ==="
bash ops/run_research_cycle.sh

echo
echo "=== WHAT THE RUN PRODUCED ==="
"$PY" - <<'PYEOF'
import json
from pathlib import Path

def show(rel, fn):
    p = Path(rel)
    if not p.exists():
        print(f"  {rel}: ABSENT -- not produced by this run")
        return
    try:
        fn(json.loads(p.read_text("utf-8")))
    except (ValueError, KeyError, TypeError) as e:
        print(f"  {rel}: unreadable ({type(e).__name__})")

def sweep(d):
    c = d.get("counts", {})
    print("  CONVERSION CHAIN (the only sequence that matters):")
    for k in ("declared", "measurable", "cleared_screen_F1_F2", "FORMULA", "FAMILY",
              "INDEPENDENT_MECHANISM", "PORTFOLIO_CONTRIBUTING"):
        v = c.get(k)
        print(f"    {k:26s} {'UNMEASURED' if v is None else v}")
    print(f"    killed cells retained     {len(d.get('killed_cells') or [])}")
    print(f"    survivor pnl sidecar      {d.get('survivor_pnl_artifact') or 'ABSENT'}")

def review(d):
    print("  KILL AUDIT :", d.get("kill_audit", {}).get("headline", "absent"))
    print("  GATE POWER :", d.get("gate_power", {}).get("headline", "absent"))
    print("  BANDS      :", d.get("failure_bands", {}).get("headline", "absent"))

def admission(d):
    print("  ADMISSION  :", d.get("verdict", "absent"))
    print(f"  PORTFOLIO_CONTRIBUTING = {d.get('PORTFOLIO_CONTRIBUTING')}")

def ladder(d):
    print("  LADDER     :", d.get("verdict", "absent"))
    print(f"  owed a shadow start: {len(d.get('to_shadow') or [])}")

def ledger(d):
    print("  LEDGER     :", d.get("headline", "absent"))
    print("  NEXT       :", d.get("next_action", "absent"))

show("data/full_sweep.json", sweep)
show("data/research_review.json", review)
show("data/portfolio_admission.json", admission)
show("data/live_ladder.json", ladder)
show("data/completion_ledger_status.json", ledger)
PYEOF

echo "=== pipeline exit $? at $(date -u) ==="
} 2>&1 | tee -a "$LOG"

echo "full log: $LOG"
