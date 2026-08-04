#!/usr/bin/env bash
# OWED-WORK WORKER v3 -- self-tuning, no invented ceiling.
#
# v2 capped the batch at 12 "because past that a run has not the context". That number was a GUESS
# wearing a justification, and the doctrine is explicit: a clamp must cite QUANTIFIED risk and
# carry an explicit lifting condition, or it is removed. It cited neither. Removed.
#
# WHAT REPLACES IT: a ratchet that finds its own ceiling from evidence. Every run records whether
# it FINISHED, hit a SESSION LIMIT, or TIMED OUT. A finished run raises the batch by 2 with no
# upper bound; a limited or timed-out run halves it and records why. So the batch climbs until
# reality objects, then settles just below whatever the real ceiling is -- and if capacity is
# raised later (a bigger seat, more RAM) it climbs again by itself with no code change. That is
# the lifting condition, built in rather than written down and forgotten.
#
# THE ONLY HARD GUARD IS PHYSICAL AND MEASURED: available RAM. Each claude run costs ~190MB and
# the box is 3.8GB with the brain, the deep sweep and the executor already resident. Below 400MB
# free this run SKIPS rather than invoking, because an OOM kill does not politely choose the
# recommendation worker -- it picks by score, and the dead-man rail is a candidate. That is not
# timidity, it is the one constraint whose breach can cost the book.
#
# FREQUENCY: every 20 minutes rather than hourly. Three chances an hour instead of one, so a
# generation burst is answered inside the hour it happens.
set -uo pipefail
cd /home/quant/quant-platform
source ops/brain_env.sh

mkdir -p data/cro_ai_logs
LOG="data/cro_ai_logs/recommendation_worker_$(date -u +%Y%m%dT%H%M).log"
TUNE="data/owed_worker_tuning.json"

AVAIL="$(free -m | awk 'NR==2{print $7}')"
if [ "${AVAIL:-0}" -lt 400 ]; then
    echo "$(date -u +%FT%TZ) owed-work: SKIP, ${AVAIL}MB free < 400MB floor. The OOM killer picks by score and the ruin rail is a candidate; this is the one guard that is physical, not preference." >> "$LOG"
    exit 0
fi

WORK="$(.venv/bin/python - <<'PYEOF'
import json, datetime as dt
from pathlib import Path

TUNE = Path("data/owed_worker_tuning.json")
try:
    t = json.loads(TUNE.read_text("utf-8"))
except Exception:
    t = {"batch": 8, "history": []}
batch = max(3, int(t.get("batch", 8)))

rows = json.loads(Path("docs/research/recommendation_ledger.json").read_text("utf-8"))["recommendations"]
now = dt.datetime.now(dt.UTC)
open_rows = [r for r in rows if r.get("status") == "open"]

def age_h(r):
    try:
        return (now - dt.datetime.fromisoformat(r["raised"])).total_seconds() / 3600.0
    except Exception:
        return 0.0

open_rows.sort(key=age_h, reverse=True)
take = open_rows[:batch]
print(f"### {len(open_rows)} rows open. Batch {batch} (self-tuned). Take ALL of these.\n")
for r in take:
    print(f"{r['id']} :: [{r.get('source')}] {r['summary'][:380]}")

try:
    rep = json.loads(Path("data/max_audit_report.json").read_text("utf-8"))
    live = [d for d in rep.get("live", []) if not str(d.get("id", "")).startswith("rec-")]
    if live:
        print(f"\n### {len(live)} live defect(s). Take ALL of them.\n")
        for d in live:
            print(f"DEFECT {d.get('id')} :: {str(d.get('msg'))[:380]}")
except Exception:
    pass
PYEOF
)"

if ! printf '%s' "$WORK" | grep -q "::"; then
    echo "$(date -u +%FT%TZ) owed-work: nothing owed" >> "$LOG"
    exit 0
fi

brain_auth_check || { echo "auth unavailable -- next run resumes" >> "$LOG"; exit 1; }

PROMPT="You are the owed-work worker. Take EVERY item below to a finished disposition. Nothing else.

${WORK}

LEDGER ROWS: implement properly (read the cited files, change the code, add or update a test where
behaviour changes, run ruff and the relevant pytest subset, commit, then dispose --status
implemented --commit <sha> --expect '<distinctive substring>'); OR reject with a substantive reason
(>=25 chars: duplicates a NAMED row, superseded, negative EV once complexity is priced, re-tests
graveyarded ground, blocked forever); OR schedule with --due and what it waits on. A reasoned no IS
a completed disposition -- the standard is that nothing is SKIPPED, not that everything is built.

DEFECTS: fix it and prove the fence goes green, or ACK it with a real reason and a <=30d expiry, or
state that it needs the principal and why. Never ack something you could have fixed in the time the
ack took to write.

HARD RULES:
  * scripts/run_deadman_switch.py is Tier-3 -- do NOT edit it; schedule such a row noting it needs
    principal sign-off.
  * Never loosen a survival rail, venue rate limit, or validation bar to make something pass.
    Editing a guard to fit the violation it caught is the failure this desk has paid for repeatedly.
  * --expect is MANDATORY on every dispose: ids shift when another writer appends.
  * Already done? Prove it with an artifact or commit and dispose it implemented citing that proof.
  * Run scripts/run_law_gate.py before your final commit; fix what YOU broke, note what was already
    breaching.
  * Anything you cannot finish honestly stays OPEN with the reason. A false 'implemented' is worse
    than an untouched row -- it removes the thing from view permanently.

Work the list top to bottom and get through as many as you honestly can. Report per item: what you
did, the sha or the reason, and anything worth its own row (scripts/recommendations.py add)."

echo "=== owed-work worker start $(date -u) ===" >> "$LOG"
# TIMEOUT IS LOAD-BEARING. This run holds the flock for its whole life, so a hang does not
# merely waste itself -- it blocks EVERY subsequent tick indefinitely. The first live run hung
# past an hour and silently deadlocked the queue while looking perfectly alive. 3000s is
# generous for a large batch at max effort and still frees the lock before the next-but-one
# tick, so the queue can never stall for more than one cycle. Exit 124 feeds the ratchet as a
# ceiling signal and halves the batch, which is correct: a run that could not finish in 50
# minutes was too big.
timeout 3000 claude --effort max --append-system-prompt "$_DOCTRINE" -p "$PROMPT" \
    --dangerously-skip-permissions >> "$LOG" 2>&1
RC=$?
if [ "$RC" = "124" ]; then
    echo "TIMED OUT after 3000s -- the ratchet halves the batch next run" >> "$LOG"
fi
echo "=== owed-work worker exit $RC at $(date -u) ===" >> "$LOG"

# RATCHET: climb on success, halve on a real ceiling. No upper bound -- the ceiling is discovered,
# never declared.
.venv/bin/python - "$LOG" "$RC" <<'PYEOF'
import json, sys, datetime as dt
from pathlib import Path
log, rc = Path(sys.argv[1]), int(sys.argv[2])
TUNE = Path("data/owed_worker_tuning.json")
try:
    t = json.loads(TUNE.read_text("utf-8"))
except Exception:
    t = {"batch": 8, "history": []}
body = log.read_text("utf-8", errors="ignore").lower()
hit_limit = "session limit" in body or "rate limit" in body or "529" in body
old = int(t.get("batch", 8))
if rc != 0 or hit_limit:
    t["batch"] = max(3, old // 2)
    why = "session/rate limit" if hit_limit else f"exit {rc}"
    t.setdefault("history", []).append({"at": dt.datetime.now(dt.UTC).isoformat(),
                                        "batch": old, "next": t["batch"], "why": why})
else:
    t["batch"] = old + 2      # no ceiling: it climbs until reality objects
    t.setdefault("history", []).append({"at": dt.datetime.now(dt.UTC).isoformat(),
                                        "batch": old, "next": t["batch"], "why": "completed"})
t["history"] = t["history"][-40:]
t["note"] = ("Self-tuning batch. Climbs by 2 on every completed run with NO upper bound, halves on "
             "a session/rate limit or non-zero exit. The ceiling is DISCOVERED from evidence, never "
             "declared -- and if capacity rises later it climbs again by itself.")
TUNE.write_text(json.dumps(t, indent=1), "utf-8")
print(f"tuning: batch {old} -> {t['batch']}")
PYEOF
