#!/usr/bin/env python3
"""§37: print the work owed from previous cycles, for the brain to do FIRST.

Run at the START of a brain cycle. It reads the sweep ledger, works out how long each open defect
has been owed and how many of those sweeps ran with the brain AWAKE, and prints a ranked brief.
Always exits 0 -- this steers priority, it never blocks a cycle.

    python3 scripts/carryover_brief.py            # the brief
    python3 scripts/carryover_brief.py --record   # append this sweep, then print
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data/carryover_sweeps.jsonl"
LOGS = ROOT / "data/cro_ai_logs"


def brain_was_alive(*, window_h: float = 26.0) -> bool:
    """Did the most recent brain cycle actually run, or die on quota?

    Read from the LOG CONTENT, not from the fact a log exists -- a cycle that dies at birth still
    creates a file, and counting that as 'alive' would blame the desk for an outage it did not
    choose. Absent any recent log at all, assume alive: over-reporting a skip is a defect the
    reader can dismiss, while silently excusing real avoidance is the failure that compounds.
    """
    from libs.ops.carryover import DEATH_MARKERS

    if not LOGS.is_dir():
        return True
    recent = [p for p in LOGS.glob("2026*_*.log")
              if (time.time() - p.stat().st_mtime) < window_h * 3600]
    if not recent:
        return True
    newest = max(recent, key=lambda p: p.stat().st_mtime)
    try:
        txt = newest.read_text("utf-8", errors="ignore").lower()
    except OSError:
        return True
    return not any(m in txt for m in DEATH_MARKERS)


#: How many stale ledger rows to hand the brain. The brief exists to be ACTED ON, so it names a
#: workable batch and states the true total -- it never truncates silently (L1.35).
_LEDGER_ROWS = 10


def ledger_block() -> str:
    """The §42/L2.3 half of the brief: recommendation rows that owe a disposition.

    WHY THIS IS HERE. The carry-over brief is the FIRST thing in every brain prompt and it carried
    only max_audit DEFECTS -- while the recommendation ledger, the organ that actually drives
    conversion, sat at 145 open rows that no prompt ever surfaced. So the desk's most-read
    prioritiser was structurally blind to its largest backlog, and L1.28b's measured finding
    (no row older than 3.67 days had EVER been implemented) is exactly what that blindness
    produces: rows nobody is shown are rows nobody works.

    THE RULE IS IMPORTED, NEVER RESTATED. `recommendations.owed()` is the one definition of
    "stale", and this calls it. The sibling defect fixed hours earlier on this same file was
    precisely a second copy of a rule drifting from its source -- the brief enumerated
    max_audit.CHECKS but kept its own idea of which were acked, and ran 57% false. Copying the
    grace/due logic here would rebuild that bug in the next drawer down.

    PAST-DUE OUTRANKS MERELY-OPEN. A scheduled row that blew its date broke an explicit commitment
    the desk made to itself; an open row has only ever been ignored. Within each class, oldest
    first.
    """
    try:
        import scripts.recommendations as rec
        d = rec._load()
        orphans, overdue = rec.owed(d)
    except Exception as exc:
        # An unreadable ledger is UNMEASURED, never "nothing owed" -- a brief that silently prints
        # an empty queue on a broken read is the most dangerous thing it could do (L1.41).
        return (f"\n[§42 LEDGER] UNMEASURED -- could not read the recommendation ledger "
                f"({type(exc).__name__}: {exc}). This is NOT 'nothing owed': treat the ledger "
                f"backlog as unknown and check scripts/recommendations.py report by hand.")

    if not orphans and not overdue:
        return ("\n[§42 LEDGER] no recommendation row owes a disposition -- "
                f"{len(d.get('recommendations', []))} row(s) on record, all disposed or in grace.")

    def _key(r: dict[str, object]) -> float:
        try:
            return -rec._age_h(r["raised"])
        except Exception:
            return 0.0

    ranked = sorted(overdue, key=_key) + sorted(orphans, key=_key)
    lines = [
        "",
        f"[§42 LEDGER] {len(orphans)} row(s) UNDISPOSED past grace, {len(overdue)} SCHEDULED past "
        "due. A row reaches a disposition or it is a DEFECT, not backlog:",
        "  implemented (--commit) | rejected (a real --reason) | scheduled (an enforced --due).",
        "  A REASONED NO IS A COMPLETED DISPOSITION. Silence is the only failure state.",
        "",
    ]
    for r in ranked[:_LEDGER_ROWS]:
        kind = "PAST-DUE" if r.get("status") == "scheduled" else "undisposed"
        try:
            age = f"{rec._age_h(r['raised']) / 24.0:.1f}d"
        except Exception:
            age = "age?"
        summary = " ".join(str(r.get("summary", "")).split())[:110]
        lines.append(f"  [{kind:11}] {r.get('id')}  {age:>6}  {summary}")
    if len(ranked) > _LEDGER_ROWS:
        lines.append(f"  ... and {len(ranked) - _LEDGER_ROWS} more owing a disposition "
                     f"(shown {_LEDGER_ROWS} of {len(ranked)} -- the rest are NOT excused).")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="append the current sweep's open defects to the ledger first")
    a = ap.parse_args()

    from libs.ops.carryover import brief, carryover_state, load_sweeps, record_sweep
    from libs.ops.lawful import guard

    guard()

    if a.record:
        try:
            import scripts.max_audit as m
            defects: list[tuple[str, str]] = []
            for _label, fn in m.CHECKS:
                m._fenced(fn, defects, _label)
            # ACK-AWARE (2026-08-01). This recorded EVERY defect as owed, including the ones the
            # desk had already disposed of with a dated, reasoned, expiring ack -- so the brief
            # accused the brain of avoidance for work it had explicitly judged and scheduled, and
            # the 12 items it ranked FIRST were 12/12 acked. Split against the ONE ack registry
            # (max_audit.split_acked), never a second copy of the rule.
            live, acked, ack_state = m.split_acked(defects)
            record_sweep(LEDGER, [d[0] for d in live], ts=time.time(),
                         brain_alive=brain_was_alive(),
                         acked_ids=[d[0] for d in acked], ack_state=ack_state)
        except Exception as exc:
            print(f"[§37] record failed ({type(exc).__name__}: {exc}) -- printing prior state")

    print(brief(carryover_state(load_sweeps(LEDGER), now=time.time())))
    print(ledger_block())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
