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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
