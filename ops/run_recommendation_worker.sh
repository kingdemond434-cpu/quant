#!/usr/bin/env bash
# OWED-WORK WORKER (principal 2026-08-01: "recommendation conversion fully aggressive, maxed, and
# immediately acted upon by the desk -- same with defects").
#
# v2 changes two things that made v1 merely adequate:
#
# 1. ADAPTIVE BATCH, NOT A FIXED 3. A constant batch is a constant drain rate, so a generation
#    burst permanently outruns it -- and the desk burst ~40 rows in one hour while I watched. The
#    batch now scales with the backlog (depth/18, floored at 3, capped at 12), so a deep queue is
#    attacked harder and a shallow one is not padded with low-value work. The cap is not timidity:
#    beyond ~12 rows one run's context stops being enough to do any of them properly, and a batch
#    that half-finishes twelve rows is worse than one that finishes eight.
#
# 2. DEFECTS ARE OWED WORK TOO. max_audit carries live defects with NO consumer -- exactly the gap
#    that let 137 recommendations pile up before this organ existed. Fixing a defect and
#    implementing a recommendation are the same act (read the evidence, change the code, prove it),
#    so they share one organ, one lock and one contract rather than spawning a third claude
#    process on a 3.8GB box.
#
# Own flock, never brain_mutex: the frontier miners took the mutex and produced nothing for ~12
# days because they deferred every time a cycle was live. A consumer that yields to a producer
# never runs.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh

mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/recommendation_worker_$(date -u +%Y%m%dT%H%M).log"

WORK="$(.venv/bin/python - <<'PYEOF'
import json, math, subprocess, datetime as dt
from pathlib import Path

rows = json.loads(Path("docs/research/recommendation_ledger.json").read_text("utf-8"))["recommendations"]
now = dt.datetime.now(dt.UTC)
open_rows = [r for r in rows if r.get("status") == "open"]

def age_h(r):
    try:
        return (now - dt.datetime.fromisoformat(r["raised"])).total_seconds() / 3600.0
    except Exception:
        return 0.0

# ADAPTIVE: attack a deep queue harder. Cap at 12 -- past that one run cannot do any of them
# properly, and half-finishing twelve is worse than finishing eight.
n = max(3, min(12, math.ceil(len(open_rows) / 18)))
open_rows.sort(key=age_h, reverse=True)
print(f"### {len(open_rows)} rows open; this run takes the {n} oldest.\n")
for r in open_rows[:n]:
    print(f"{r['id']} :: [{r.get('source')}] {r['summary'][:380]}")

# Live max_audit defects share the batch: same act, same contract, no third process.
try:
    rep = json.loads(Path("data/max_audit_report.json").read_text("utf-8"))
    live = [d for d in rep.get("live", []) if not str(d.get("id", "")).startswith("rec-")]
    if live:
        print(f"\n### {len(live)} live max_audit defect(s); this run takes the 3 oldest.\n")
        for d in live[:3]:
            print(f"DEFECT {d.get('id')} :: {str(d.get('msg'))[:380]}")
except Exception:
    pass
PYEOF
)"

if ! printf '%s' "$WORK" | grep -q "::"; then
    echo "$(date -u +%FT%TZ) owed-work worker: nothing owed" >> "$LOG"
    exit 0
fi

brain_auth_check || { echo "auth unavailable -- next run resumes" >> "$LOG"; exit 1; }

PROMPT="You are the owed-work worker. Take every item below to a real, finished disposition. That
is your whole job this run -- do not start anything else.

${WORK}

FOR EACH LEDGER ROW: implement it properly (read the cited files, make the change, add or update a
test where behaviour changes, run ruff and the relevant pytest subset, commit, then dispose with
--status implemented --commit <sha> --expect '<distinctive substring>'); OR reject it with a
substantive reason (>=25 chars: duplicates a named row, superseded, negative EV once complexity is
priced, re-tests graveyarded ground, blocked forever); OR schedule it with --due and say what it
waits on. A reasoned no IS a completed disposition -- the standard is that nothing is SKIPPED, not
that everything is built.

FOR EACH DEFECT: fix it and prove the fence goes green, or ACK it in data/max_audit_acks.json with
a real reason and an expiry no more than 30 days out, or state plainly that it needs the principal
and why. Never ack something you could have fixed in the time it took to write the ack.

HARD RULES, and these are not negotiable:
  * scripts/run_deadman_switch.py is Tier-3. Do NOT edit it. A row needing it gets scheduled with
    a note that it needs principal sign-off.
  * Never loosen a survival rail, a venue rate limit, or a validation bar to make something pass.
    Editing a guard to fit the violation it just caught is the failure this desk has paid for
    repeatedly.
  * --expect is MANDATORY on every dispose. Ids shift when another writer appends, and disposing
    the wrong row is worse than leaving it open.
  * If a row is already done, prove it with a real artifact or commit and dispose it implemented
    citing that proof -- do not re-implement it.
  * Run .venv/bin/python scripts/run_law_gate.py before your final commit. Fix anything YOU broke;
    if a breach was already there, say so and proceed.
  * A row you cannot finish honestly stays OPEN with the reason stated. A false 'implemented' is
    far worse than an untouched row, because it removes the thing from view permanently.

Report per item: what you did, the commit sha or the reason, and anything you noticed that
deserves its own row (add it with scripts/recommendations.py add)."

echo "=== owed-work worker start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$PROMPT" \
    --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== owed-work worker exit $? at $(date -u) ===" >> "$LOG"
