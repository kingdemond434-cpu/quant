#!/usr/bin/env bash
# RECOMMENDATION WORKER (principal 2026-08-01: "make claude keep up with recommendation
# implementations, immediate, automated").
#
# THE GAP IT CLOSES. §41 made every recommendation reach a disposition, and the desk then generated
# them faster than anything consumed them: 132 open, 51 past the 24h grace, oldest 39h, and ZERO
# cron organs touching the ledger. Generation without a matching consumer is not throughput, it is
# a queue that grows until nobody reads it -- which is precisely the failure §41 was built to stop,
# arriving one layer up. The brain triages the ledger among a dozen other duties and loses.
#
# WHY ITS OWN LOCK, NOT THE BRAIN MUTEX. The frontier miners took brain_mutex and starved: every
# time their timer fired the brain held it, they deferred instantly, and in ~12 days they produced
# nothing. A worker that defers to a busy organ is a worker that never runs. This takes its own
# flock so it runs CONCURRENTLY with the brain, capped at one instance. Two claude processes at
# ~190MB against 1.6GB available is affordable; a permanently starved queue is not.
#
# BATCH SIZE 3, deliberately small. A large batch means one bad row poisons a long run and the
# whole commit gets reverted; three keeps each run short, keeps the diff reviewable, and at hourly
# cadence clears 72/day against a generation rate near 50/day -- so the backlog drains rather than
# merely holding steady.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh

mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/recommendation_worker_$(date -u +%Y%m%dT%H%M).log"

# Oldest-first among rows past their grace window: age is the honest priority when every row
# already carries an ERV note, and it guarantees nothing can sit forever because newer work keeps
# looking more attractive.
BATCH="$(.venv/bin/python - <<'PYEOF'
import json, datetime as dt
from pathlib import Path
rows = json.loads(Path("docs/research/recommendation_ledger.json").read_text("utf-8"))["recommendations"]
now = dt.datetime.now(dt.UTC)
open_rows = [r for r in rows if r.get("status") == "open"]
def age_h(r):
    try:
        return (now - dt.datetime.fromisoformat(r["raised"])).total_seconds() / 3600.0
    except Exception:
        return 0.0
open_rows.sort(key=age_h, reverse=True)
for r in open_rows[:3]:
    print(f"{r['id']} :: [{r.get('source')}] {r['summary'][:400]}")
PYEOF
)"

if [ -z "$BATCH" ]; then
    echo "$(date -u +%FT%TZ) recommendation-worker: ledger clear, nothing owed" >> "$LOG"
    exit 0
fi

brain_auth_check || { echo "auth unavailable -- next run resumes" >> "$LOG"; exit 1; }

PROMPT="You are the recommendation worker. Your ONLY job this run is to take the three ledger rows
below to a real disposition. Nothing else.

${BATCH}

FOR EACH ROW, do exactly one of:
  IMPLEMENT it properly -- read the cited files, make the change, add or update a test where the
    change is behavioural, run: .venv/bin/python -m ruff check libs/ scripts/ tests/ and the
    relevant pytest subset. Then commit (never --no-verify) and dispose:
      .venv/bin/python scripts/recommendations.py dispose --id <ID> --status implemented \\
        --commit <sha> --expect '<a distinctive substring of that row summary>'
  REJECT it with a substantive reason (>=25 chars) -- duplicates another row (name it), superseded,
    negative EV once complexity is priced, re-tests graveyarded ground, or blocked forever on
    something that will not happen. A reasoned no IS a completed disposition; the standard is that
    nothing is SKIPPED, not that everything is built.
  SCHEDULE it with --due YYYY-MM-DD and say what it waits on. Use this sparingly: a scheduled row
    that nothing unblocks is a rejection wearing a nicer label.

HARD RULES:
  * scripts/run_deadman_switch.py is Tier-3. Do NOT edit it. If a row requires it, dispose the row
    as scheduled and say it needs principal sign-off.
  * Never loosen a survival rail, a venue rate limit, or a validation bar to make a row pass.
  * If a row is already done, verify that with a real artifact or commit and dispose it
    implemented citing the proof -- do not re-implement it.
  * --expect is mandatory on every dispose: ids shift when another writer appends, and disposing
    the wrong row is worse than leaving it open.
  * Run .venv/bin/python scripts/run_law_gate.py before your final commit. If it breaches on
    something YOU changed, fix it; if it was already breaching, say so and proceed.
  * If you cannot finish a row honestly, leave it OPEN and say why. A false 'implemented' is far
    worse than an untouched row, because it removes the thing from view forever.

Report per row: what you did, the commit sha or the reason, and anything you noticed that deserves
its own ledger row (add it with scripts/recommendations.py add)."

echo "=== recommendation-worker start $(date -u) ===" >> "$LOG"
claude --effort max --append-system-prompt "$_DOCTRINE" -p "$PROMPT" \
    --dangerously-skip-permissions >> "$LOG" 2>&1
echo "=== recommendation-worker exit $? at $(date -u) ===" >> "$LOG"
