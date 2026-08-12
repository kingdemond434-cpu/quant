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

#: Missed deadlines past which a re-deferred row needs a DECISION rather than another date. One
#: miss followed by a dated re-commitment is the register working; a second is a treadmill, and
#: the count is the only thing that can tell them apart. A COUNT, deliberately, not a duration --
#: L1.48 forbids gating on elapsed calendar time, and how many promises a row has broken is
#: evidence in a way that how long it has been open is not.
TREADMILL_MISSES = 2

#: Verdicts that mean a human has to decide something. RE-DEFERRED is here only past the
#: treadmill count: a row that re-committed once has taken a legal exit and listing it would
#: punish the honest act this change exists to make possible.
_NEEDS_DECISION = ("DEADLINE-PASSED", "PARKED", "UNOWNED", "STARVED")


def needs_decision(r: dict) -> bool:
    return (r["verdict"] in _NEEDS_DECISION
            or (r["verdict"] == "RE-DEFERRED"
                and r.get("missed_deadlines", 0) >= TREADMILL_MISSES))


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
    parsed = parse_register(text)
    # An id that names two rows breaks the register's ADDRESSING, which is the one thing every
    # other organ relies on: the desk-state hook prints "#100", the doctrine says "row 91 is the
    # current top item", and a citation that resolves to two different findings is not a citation.
    seen: dict[int, int] = {}
    for r in parsed:
        seen[r.row_id] = seen.get(r.row_id, 0) + 1
    ambiguous = {k: v for k, v in seen.items() if v > 1}
    rows = []
    for r in parsed:
        if not r.is_open:
            continue
        deadlines = sorted({date.fromisoformat(x) for x in _DEADLINE_RE.findall(r.body)
                            if _valid_iso(x)})
        # BOTH FACTS, NEVER ONE. `min()` over every date in a row let the FIRST missed deadline
        # dominate forever, so a row re-deferred with a new dated reason -- one of the register's
        # three legal exits -- printed DEADLINE-PASSED anyway and could be cleared only by
        # deleting the old date, which erases the miss (the denominator trick §34 forbids). The
        # current promise is the NEAREST date still ahead; the misses are carried as a count, so
        # a row on its fourth re-deferral is LOUDER under this scheme rather than quieter.
        #
        # Nearest-future, NOT latest: row #64 carries 2026-08-15 and 2026-11-15, and ranking on
        # the latest would hide a near milestone behind a far backstop -- a loosening, and the
        # reason the obvious `max()` is wrong here.
        missed = [d for d in deadlines if d < today]
        ahead = [d for d in deadlines if d >= today]
        worst = ahead[0] if ahead else (missed[0] if missed else None)
        added = _added_date(r.added)
        age = float((today - added).days) if added else -1.0
        if ahead and missed:
            verdict, why = "RE-DEFERRED", (
                f"{len(missed)} deadline(s) missed ({', '.join(d.isoformat() for d in missed)}), "
                f"now promised {ahead[0].isoformat()}. Re-deferring with a NEW dated reason is a "
                "legal exit; doing it repeatedly is a treadmill, which is what the count is for.")
        elif missed and not ahead:
            verdict, why = "DEADLINE-PASSED", (
                f"promised {missed[0].isoformat()}, now {today.isoformat()} -- a deferral whose "
                "date has passed is not deferred, it is parked with extra steps. Implement, "
                "re-defer with a NEW dated reason, or retire it."
                + (f" {len(missed)} deadlines missed on this row." if len(missed) > 1 else ""))
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
            # The miss history, kept beside the current promise rather than instead of it.
            "missed_deadlines": len(missed),
            "missed": [d.isoformat() for d in missed],
            # Reported as a FLAG, not a verdict: 34 rows collide today, and making that a verdict
            # would bury the 9 genuine deadline misses under a numbering accident.
            "id_ambiguous": r.row_id in ambiguous,
        })
    # RE-DEFERRED sits directly below DEADLINE-PASSED, never at the bottom. A row that missed a
    # date and re-committed is still the desk's most urgent class; sinking it to ON-CLOCK would
    # buy the honesty of the miss count at the price of the urgency it is evidence of.
    order = {"DEADLINE-PASSED": 0, "RE-DEFERRED": 1, "PARKED": 2, "UNOWNED": 3, "STARVED": 4,
             "ON-CLOCK": 5, "TRACKED": 6}
    rows.sort(key=lambda x: (order.get(x["verdict"], 9), -x["missed_deadlines"],
                             -x["age_days"], x["id"]))
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
    need = [r for r in rows if needs_decision(r)]
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

    need = [r for r in rows if needs_decision(r)]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 2),
        "open_rows": len(rows),
        "need_decision": len(need),
        "by_verdict": {v: sum(1 for r in rows if r["verdict"] == v)
                       for v in ("DEADLINE-PASSED", "RE-DEFERRED", "PARKED", "UNOWNED",
                                 "STARVED", "ON-CLOCK", "TRACKED")},
        "rows": rows,
        # Reported, because until the ids are unique every citation of one is ambiguous and this
        # organ has no authority to renumber the register. Silence here would leave the register
        # looking addressable while two organs reading "#100" reach different findings.
        "ambiguous_ids": sorted({r["id"] for r in rows if r["id_ambiguous"]}),
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
    if out["ambiguous_ids"]:
        print(f"  AMBIGUOUS IDS: {len(out['ambiguous_ids'])} open row(s) share an id with "
              f"another row -- {', '.join('#' + str(i) for i in out['ambiguous_ids'][:12])}"
              f"{' ...' if len(out['ambiguous_ids']) > 12 else ''}. Every citation of these "
              "resolves to two findings; renumber them in the register.")
    for r in rows[:6]:
        print(f"  [{r['verdict']:<15}] #{r['id']:<3} {r['title'][:62]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
