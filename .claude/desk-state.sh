#!/bin/bash
# SessionStart: print LIVE desk state so a fresh context starts oriented, not blind.
#
# WHY THIS EXISTS AND WHY IT IS NOT MORE CLAUDE.md. CLAUDE.md is loaded every session and is the
# right place for things that do not change: which documents bind, which laws get broken, how to
# run the gates. It is the WRONG place for numbers. A hand-written "coverage is 92.46%" is correct
# on the day it is typed and quietly wrong afterwards, and a stale number in an always-loaded file
# is worse than no number -- it is confidently misleading in every future session.
#
# So: CLAUDE.md carries the map, this carries the odometer. Everything below is READ AT SESSION
# START from the artifacts themselves, so it cannot go stale.
#
# NEVER FAILS THE SESSION. Every read is guarded and every failure prints a marker rather than
# staying silent, because a hook that dies quietly leaves the session blind while looking fine --
# which is the same absence-reads-as-health defect the desk keeps finding in its own organs.
set -uo pipefail
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT" 2>/dev/null || exit 0

PY=""
for c in "$ROOT/.venv/bin/python" .venv/bin/python python3; do
    if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done

echo "=== DESK STATE (read live at session start; CLAUDE.md has the map) ==="

if [ -n "$PY" ]; then
"$PY" - <<'PYEOF' 2>/dev/null || echo "  desk-state: python read FAILED -- treat every number below as UNKNOWN, not as fine"
import json, os
from datetime import UTC, datetime

def j(p):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return None

r = j("docs/research/COVERAGE_RATCHET.json") or {}
hw, ms = r.get("high_water", {}), r.get("measured", {})
if hw:
    print(f"  coverage   repo {ms.get('repo_pct','?')}% (floor {hw.get('repo_pct','?')}%) | "
          f"money path {ms.get('money_path_pct','?')}% (floor {hw.get('money_path_pct','?')}%)")
    lr = r.get("last_raised")
    if lr:
        try:
            age = (datetime.now(tz=UTC) - datetime.fromisoformat(lr)).days
            print(f"             last raised {age}d ago" + ("  <-- L1.50 STALL" if age >= 14 else ""))
        except Exception: pass
    else:
        print("             last_raised ABSENT -- L1.50: absent is not clean")

# The 40-day forward clock. Distinct UTC days in the archive IS the clock; the venue caps
# openInterestHist at ~30d so it can only be accrued, never backfilled.
p = "data/oi_ls_live.jsonl"
if os.path.exists(p):
    days = set()
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try: days.add(json.loads(line).get("ts", "")[:10])
                except Exception: pass
    except Exception: days = set()
    d = len(days - {""})
    print(f"  oi/ls clock  {d}/40 distinct days"
          + ("  MATURE -- now needs t>=1.65" if d >= 40 else f"  ~{40-d}d to go"))
else:
    print("  oi/ls clock  archive ABSENT on this clone (data/ is gitignored -> it is on the VPS)")

st = j("data/failed_breakout_study.json")
if st: print(f"  study        failed_breakout: {str(st.get('verdict','?'))[:60]}")
else:  print("  study        failed_breakout: NO ARTIFACT -- 0 of 16,200 trials executed")

# REASONING DEPTH. `libs.llm.effort.coverage()` existed with ZERO non-test callers, so the one
# number it computes -- how many seats run on the 'high' FALLBACK instead of the deepest rung they
# advertise -- was never read by anyone. Every such seat is a flagship being asked a shallower
# question than it can answer, and the call succeeds either way, so the cost surfaces nowhere on
# its own. It is on the odometer now for the same reason coverage is.
caps = j("data/roster_capabilities.json")
if caps:
    models = sorted((caps.get("models") or caps).keys())
    try:
        from libs.llm.effort import coverage as _cov
        c = _cov(models)
        print(f"  llm depth    {c['measured']}/{c['models']} seats at their advertised max, "
              f"{c['fallback']} on the 'high' fallback"
              + ("  <-- under-driven; refresh_panel_roster" if c["fallback"] else ""))
    except Exception:
        print("  llm depth    roster present but unreadable -- depth UNKNOWN, not fine")
else:
    print("  llm depth    roster capabilities ABSENT -> EVERY seat runs on the 'high' fallback, "
          "not its advertised max. Run scripts/refresh_panel_roster.py on the box.")
PYEOF
else
    echo "  desk-state: no python found -- state UNKNOWN, not fine"
fi

if [ -f docs/GAP_REGISTER.md ]; then
    echo "  top open gap rows (docs/GAP_REGISTER.md):"
    grep -oE '^\| [0-9]+ \| \*\*[^*]{1,95}' docs/GAP_REGISTER.md 2>/dev/null \
      | sed 's/^| /    #/; s/ | \*\*/  /' | tail -3
fi
# SHARED-CHECKOUT WARNING (R0423). Printed HERE because session start is the one moment the
# decision is still free -- once you have edited the tree, taking a worktree costs a migration.
# Three recorded instances of a sibling's broad `git commit` sweeping another session's staged
# files into an unrelated commit; the code survived every time and the RATIONALE did not.
# ADVISORY ONLY: it never fails the session (L1.37 -- a governance fault must not stop the desk).
if [ -n "$PY" ]; then
    "$PY" - <<'PYEOF' 2>/dev/null || true
try:
    from libs.ops.shared_tree import detect
    r = detect()
    if r["status"] == "SHARED":
        pids = ", ".join(str(o["pid"]) for o in r["same_worktree"])
        print(f"  SHARED TREE  {len(r['same_worktree'])} other live session(s) in THIS worktree "
              f"(pid {pids})")
        print("               a broad `git commit` in either sweeps the other's staged files. "
              "Stage explicit paths,")
        print("               or take your own:  git worktree add -b <branch> ../qp-<branch>"
              "   (never `git stash`)")
    elif r["status"] == "UNMEASURED":
        print(f"  shared tree  UNMEASURED -- {r['detail'][:90]}")
except Exception:
    print("  shared tree  detector unreadable -- concurrency UNKNOWN, not fine")
PYEOF
fi
echo "  READ FIRST: CLAUDE.md, then docs/GAP_REGISTER.md row 91 (the ranked top item)."
echo "=========================================================================="
