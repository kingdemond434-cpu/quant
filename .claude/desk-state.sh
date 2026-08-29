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

# The 40-day forward clock. Distinct UTC days in the archive IS the clock -- but a FROZEN
# archive and an accruing one produce the identical count, so the count alone is a liveness
# claim the desk cannot cash. Until 2026-08-29 this printed "23/40 ~17d to go" to every session
# for 8 days after its collector died with root cron (2026-08-20T20:32Z), which is the desk's
# own "heartbeat liveness != data liveness" lesson reappearing on its own front page.
# Two facts now travel with the number: how OLD the newest observation is, and that the feed is
# fapi.binance.com (scripts/collect_oi_ls_live.py:42) -- BANNED ground under LAWS s1, so this
# clock can never legitimately mature and must not be resurrected.
p = "data/oi_ls_live.jsonl"
if os.path.exists(p):
    days, newest = set(), ""
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    ts = json.loads(line).get("ts", "")
                except Exception:
                    continue
                if ts:
                    days.add(ts[:10])
                    if ts > newest: newest = ts
    except Exception:
        days, newest = set(), ""
    d = len(days - {""})
    age_h = None
    if newest:
        try:
            age_h = (datetime.now(UTC) - datetime.fromisoformat(newest)).total_seconds() / 3600.0
        except Exception:
            age_h = None
    if age_h is None:
        state = "UNMEASURED -- no parseable timestamp; count is not a clock"
    elif age_h > 36:
        state = f"FROZEN {age_h/24:.1f}d (banned-universe feed; RETIRED, never resurrect)"
    else:
        state = "MATURE -- now needs t>=1.65" if d >= 40 else f"~{40-d}d to go"
    print(f"  oi/ls clock  {d}/40 distinct days  {state}")
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
# III.16 -- UNWIRED OR IDLE IS A DEFECT, surfaced at session start so every Claude session sees
# the number before it decides what to build. A capability written, tested and correct but CALLED
# BY NOTHING is invisible to ruff, mypy, the suite and any module count; the only question that
# separates it from a working one is WHAT RAN IT, and it is never asked by accident. Read from the
# artifact rather than recomputed here: a number typed into a hook is correct the day it is typed.
if [ -f data/unwired_capability.json ]; then
    "$PY" - <<'PYEOF' 2>/dev/null || true
import json
try:
    d = json.load(open("data/unwired_capability.json"))
    n, t = int(d.get("n_suspects", 0)), int(d.get("n_tested_but_unwired", 0))
    if n:
        print(f"  unwired      {n} public capability(ies) called by NOTHING; {t} of them TESTED "
              f"but wired to nothing (III.16)")
        print( "               `python scripts/check_unwired_capability.py` -- built is not a "
               "status; name the caller")
except Exception:
    print("  unwired      report unreadable -- III.16 compliance UNKNOWN, not clean")
PYEOF
else
    echo "  unwired      data/unwired_capability.json ABSENT -- the III.16 hunter has not run here"
fi
# THE FENCE RED LIST (wired 2026-08-29). ~70 dead cron rows run under the manifest dispatcher
# since the 08-20 root-cron OOM death, and ~30 of them are fences whose contract is to exit 2 on a
# real finding. The dispatcher detached every one of them with stdout on DEVNULL and collected no
# exit code, so `check_organ_liveness: DARK (32 dead organs)` and `check_bar_span: CONTAMINATED
# 88/88` existed only inside unread logs. The dispatcher now records each row's rc; this surfaces
# the roll-up where every session already looks. The DENOMINATOR travels with it on purpose: 0 red
# over 0 recorded is an unmeasured fleet, not a healthy one, and the two must never render alike.
if [ -f data/manifest_dispatch_state.json ]; then
    "$PY" - <<'PYEOF2' 2>/dev/null || true
import json
try:
    d = json.load(open("data/manifest_dispatch_state.json"))
    reds, rec = d.get("red_rows") or {}, d.get("outcomes_recorded_n")
    if rec is None:
        print("  fences       exit codes NOT RECORDED -- dispatcher predates the rc wiring; "
              "fence health UNMEASURED, not clean")
    elif int(rec) == 0:
        print("  fences       0 of 0 rows reported an exit code in 26h -- UNMEASURED "
              "(a dispatcher that fired nothing looks identical to a healthy fleet)")
    else:
        names = ", ".join(sorted(reds)[:3]).replace("scripts/", "")
        tail = f" -- {names}{' ...' if len(reds) > 3 else ''}" if reds else ""
        print(f"  fences       {len(reds)} RED of {rec} rows reporting in 26h{tail}")
except Exception:
    print("  fences       dispatch state unreadable -- fence health UNKNOWN, not clean")
PYEOF2
fi
# DOCUMENT DESTRUCTION, COUNTED WHERE SOMEONE READS IT (wired 2026-08-29). The replay fence
# heals a guarded ledger every minute and records each heal in its own log -- and on 2026-08-29 it
# logged 31 heals of docs/GAP_REGISTER.md between 03:38 and 03:54, then went quiet, because at
# 04:22 the stale content was COMMITTED and a fence that heals FROM HEAD cannot see a bad HEAD.
# 87 rows were gone by then. Nothing read that log, and the unit's exit code is the wrong channel:
# a unit permanently parked in `failed` is a unit nobody reads. A heal is a SYMPTOM of an upstream
# writer, so the count belongs where every session already looks.
if [ -f data/doc_replay_fence.log ]; then
    "$PY" - <<'PYEOF3' 2>/dev/null || true
import re
from datetime import UTC, datetime, timedelta
try:
    cut = datetime.now(UTC) - timedelta(hours=24)
    heals = {"REPLAY HEALED": 0, "DESTROYED": 0, "EMPTIED": 0}
    files = set()
    with open("data/doc_replay_fence.log", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r"(\S+) (REPLAY HEALED|DESTROYED|EMPTIED) (\S+?):", line)
            if not m:
                continue
            try:
                when = datetime.fromisoformat(m.group(1))
            except ValueError:
                continue
            if when >= cut:
                heals[m.group(2)] += 1
                files.add(m.group(3))
    n = sum(heals.values())
    if n:
        bad = heals["DESTROYED"] + heals["EMPTIED"]
        print(f"  doc heals    {n} in 24h over {len(files)} guarded file(s)"
              + (f" -- {bad} DESTRUCTION(S), not replays" if bad else " (stale-snapshot replays)")
              + " <-- an upstream writer is trampling this tree; the heal is the symptom")
except Exception:
    print("  doc heals    fence log unreadable -- tramble rate UNKNOWN, not zero")
PYEOF3
fi
echo "  READ FIRST: CLAUDE.md, then docs/GAP_REGISTER.md row 91 (the ranked top item)."
echo "=========================================================================="
