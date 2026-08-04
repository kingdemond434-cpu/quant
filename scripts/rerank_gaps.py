#!/usr/bin/env python3
"""THE MECHANICAL HALF OF THE GAP-REGISTER RE-RANK -- every cycle, seconds, no LLM.

WHY. docs/GAP_REGISTER.md is, by the doctrine's own words, "the only organ that DRIVES work":
§35 routes every finding into it and §36 holds it to its own stated cadence. That cadence --
"re-ranked at the START of every daily AI cycle" -- was executed by an LLM remembering to do it,
which run_cadence's own docstring already names as the reliability hole it exists to close:
"cadence by LLM memory is a reliability hole". It has been seven days with fifty open rows.

THE TRAP THIS ORGAN IS BUILT AROUND, AND IT IS THE WHOLE DESIGN. `register_health` reads the
self-declared `Re-ranked <date>` stamp to decide whether the duty was done. An organ that writes
that stamp after doing only the countable part would turn the check green while the judgment half
-- re-prioritising rows against NEW EVIDENCE -- never happened. That is a check-defeating organ,
which is worse than no organ at all: the defect stops being reported and the work stops being
done, at the same moment, and the second fact is invisible.

So the duty is SPLIT and the two halves are separately accountable, exactly as constitutional
enforcement splits mechanical from interactional cover:

  MECHANICAL (here, every cycle)  deadlines parsed and checked, parked rows named, staleness
                                  computed, rows ordered by signals that need no opinion. Writes
                                  data/gap_rerank.json and its OWN stamp, which deliberately does
                                  not match the re-rank regex.
  JUDGMENT (the cycle, an LLM)    re-prioritise on evidence produced since the last pass. Keeps
                                  the `Re-ranked` stamp and its own clock. Nothing here can
                                  discharge it.

WHAT THE MECHANICAL PASS BUYS. The judgment pass stops being a blank-page task. It arrives with
every deadline already checked, every parked row already named, and the rows it must actually
think about already separated from the rows that only needed arithmetic -- which is the
difference between a duty that gets skipped on a busy cycle and one that does not.

Read-only over docs/. Writes one artifact and one clearly-labelled stamp line.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.finding_registry import parse_register, register_health  # noqa: E402

REGISTER = ROOT / "docs/GAP_REGISTER.md"
REPORT = ROOT / "data/gap_rerank.json"
HISTORY = ROOT / "data/gap_rerank_history.jsonl"

#: Deadlines an open row states in its plan. The register's three legal exits are implement,
#: defer WITH A DEADLINE, or retire with a reason -- so a date in the plan is a PROMISE, and a
#: promise nobody checks is how a deferral becomes a park.
_DEADLINE_RE = re.compile(r"(?:DEADLINE|DEFERRED WITH DEADLINE|by|due)\s+(\d{4}-\d{2}-\d{2})",
                          re.IGNORECASE)

#: The mechanical stamp. Deliberately NOT matching `Re-ranked <date>`: writing that would clear
#: register_health's staleness check on a pass that did none of the judgment, which is the exact
#: failure this organ is designed not to be.
_STAMP = "_Mechanical gap-pass"

#: Row age past which the mechanical pass promotes it regardless of anything else. Same discipline
#: as the allocator's starvation rule: priority decides ORDER, never entitlement, and a row that
#: is always ranked twentieth is being permanently neglected by a rule that believes it is merely
#: ordering.
STARVATION_DAYS = 21.0


def _row_text(text: str, row_id: int) -> str:
    """The full table line for a row, so the plan column can be searched for a deadline."""
    for line in text.splitlines():
        if line.startswith(f"| {row_id} |"):
            return line
    return ""


def _added_date(added: str) -> date | None:
    """Rows carry MM-DD; the register has run for less than a year, so the year is the current one
    unless that puts the date in the future, in which case it is last year."""
    try:
        m, d = (int(x) for x in added.strip().split("-")[:2])
    except (ValueError, IndexError):
        return None
    today = datetime.now(tz=UTC).date()
    try:
        cand = date(today.year, m, d)
    except ValueError:
        return None
    return cand if cand <= today else date(today.year - 1, m, d)


def classify(text: str, today: date) -> list[dict]:
    """Every open row with the facts a re-rank needs, and none of the opinions it needs.

    Each verdict below is computable from the register alone. Nothing here weighs one row's
    importance against another's -- that is the judgment half, and pretending otherwise is how a
    mechanical pass quietly becomes a bad re-rank.
    """
    rows = []
    for r in parse_register(text):
        if not r.is_open:
            continue
        line = _row_text(text, r.row_id)
        deadlines = [date.fromisoformat(x) for x in _DEADLINE_RE.findall(line)
                     if _valid_iso(x)]
        worst = min(deadlines) if deadlines else None
        added = _added_date(r.added)
        age = float((today - added).days) if added else -1.0
        if worst and worst < today:
            verdict, why = "DEADLINE-PASSED", (
                f"promised {worst.isoformat()}, now {today.isoformat()} -- a deferral whose date "
                "has passed is not deferred, it is parked with extra steps. Implement, re-defer "
                "with a NEW dated reason, or retire it.")
        elif not r.plan_has_date:
            verdict, why = "PARKED", (
                "no date anywhere in the plan, so the row took none of the register's three legal "
                "exits (implement / defer WITH A DEADLINE / retire with reason)")
        elif not r.owner:
            verdict, why = "UNOWNED", "no owner, so the escalation has no addressee"
        elif age >= STARVATION_DAYS:
            verdict, why = "STARVED", (
                f"open {age:.0f} days. Priority decides ORDER, never entitlement -- a row always "
                "ranked below the fold is being neglected by a rule that believes it is ordering.")
        elif worst:
            verdict, why = "ON-CLOCK", f"deadline {worst.isoformat()} in {(worst - today).days}d"
        else:
            verdict, why = "TRACKED", "dated plan, owned, inside the staleness bar"
        rows.append({
            "id": r.row_id, "title": r.title[:80], "owner": r.owner, "added": r.added,
            "status": r.status, "age_days": age, "verdict": verdict, "why": why,
            "deadline": worst.isoformat() if worst else None,
        })
    order = {"DEADLINE-PASSED": 0, "PARKED": 1, "UNOWNED": 2, "STARVED": 3,
             "ON-CLOCK": 4, "TRACKED": 5}
    rows.sort(key=lambda x: (order.get(x["verdict"], 9), -x["age_days"], x["id"]))
    return rows


def _valid_iso(s: str) -> bool:
    try:
        date.fromisoformat(s)
    except ValueError:
        return False
    return True


def stamp_line(rows: list[dict], today: date) -> str:
    """The mechanical stamp -- and its wording is load-bearing.

    It states what was NOT done. A stamp that read like a re-rank would be believed like one, by a
    human skimming and by any future check that pattern-matches loosely, and the duty would be
    discharged by a pass that never weighed a single row against another.
    """
    need = [r for r in rows if r["verdict"] in ("DEADLINE-PASSED", "PARKED", "UNOWNED", "STARVED")]
    return (
        f"{_STAMP} {today.isoformat()}: {len(rows)} open rows checked mechanically -- "
        f"{len(need)} need a decision "
        f"({', '.join('#' + str(r['id']) for r in need[:12])}"
        f"{' ...' if len(need) > 12 else ''}). "
        "This is NOT a re-rank: no row was weighed against another and no new evidence was "
        "considered. The judgment pass and its `Re-ranked` stamp are still owed._")


def main() -> int:
    t0 = time.time()
    if not REGISTER.exists():
        print("gap-rerank: docs/GAP_REGISTER.md absent -- nothing to drive")
        return 0
    text = REGISTER.read_text("utf-8")
    today = datetime.now(tz=UTC).date()
    rows = classify(text, today)
    health = register_health(text, today=today)

    need = [r for r in rows if r["verdict"] in ("DEADLINE-PASSED", "PARKED", "UNOWNED", "STARVED")]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "open_rows": len(rows),
        "need_decision": len(need),
        "by_verdict": {v: sum(1 for r in rows if r["verdict"] == v)
                       for v in ("DEADLINE-PASSED", "PARKED", "UNOWNED", "STARVED",
                                 "ON-CLOCK", "TRACKED")},
        "rows": rows,
        # The judgment half's state, reported here so one artifact answers "is the register being
        # driven?" -- never so this organ can be mistaken for having done it.
        "judgment_rerank_age_days": health.rerank_age_days,
        "judgment_rerank_owed": bool(health.rerank_stale or health.rerank_breach),
        "stamp": stamp_line(rows, today),
        "note": ("MECHANICAL HALF ONLY. Deadlines, parked rows, ownership and starvation are "
                 "computable and are computed here every cycle. Re-prioritising rows against new "
                 "evidence is judgment, keeps its own `Re-ranked` stamp, and nothing in this "
                 "organ can discharge it -- an organ that cleared a check it had not satisfied "
                 "would stop the defect being reported and the work being done at the same "
                 "moment, and only the first of those is visible."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "open_rows": len(rows),
                             "need_decision": len(need)}, separators=(",", ":")) + "\n")

    print(f"gap-rerank: {len(rows)} open rows | {len(need)} need a decision | "
          f"judgment re-rank {health.rerank_age_days:.0f}d old | {out['seconds']}s")
    for r in rows[:6]:
        print(f"  [{r['verdict']:<15}] #{r['id']:<3} {r['title'][:62]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
