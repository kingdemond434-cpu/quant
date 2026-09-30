#!/usr/bin/env python3
"""FOREST-ATTEMPT FENCE: every deep-forest ground attempted daily, never-attempted falling to zero.

An hourly CORE leg (`hourly_cycle:forest_attempts`). One pass:

  1. composes every registered ground's attempt state (`desks/mt5/research/forest_attempts.py`)
     from the miner's own per-ground ledgers -- attempts, last_attempt, last_yield, failure
     reason, the delta cursor, and LOW_EV_RETIRED with its evidence and reopen condition;
  2. writes `desks/mt5/reports/FOREST_ATTEMPTS.json` and appends one line to
     `desks/mt5/data/forest_attempt_history.jsonl` -- attempted / never-attempted / yielded /
     retired / overdue, hourly, so the direction is on disk rather than in a memory;
  3. judges it: RED (exit 1) when never-attempted is positive and did not fall over the last
     day, when grounds overdue for their daily attempt did not fall over two days, or when the
     miner's counters went silent while grounds are still unattempted. UNMEASURED (exit 0, said
     in words) when the registry or the history cannot support a verdict yet -- never a green.

    python scripts/check_forest_attempts.py
    python scripts/check_forest_attempts.py --json
    python scripts/check_forest_attempts.py --dry-run     # judge, write nothing
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import forest_attempts as fa  # type: ignore[import-not-found]  # noqa: E402

#: The artifact this leg writes (the same path `forest_attempts.ARTIFACT` binds), declared here
#: so the component registry and the runtime attestation read it from the organ's own file.
OUT = ROOT / "desks" / "mt5" / "reports" / "FOREST_ATTEMPTS.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = fa.publish(out=OUT, write=not a.dry_run)
    verdict = doc.get("fence") or {}
    if a.json:
        print(json.dumps({"summary": doc.get("summary"), "fence": verdict}, indent=1,
                         default=str))
    else:
        s = doc.get("summary") or {}
        print(f"forest attempts: {verdict.get('status')}  named={s.get('named')} "
              f"never_attempted={s.get('never_attempted')} attempted_24h={s.get('attempted_24h')} "
              f"overdue_24h={s.get('overdue_24h')} yielded={s.get('yielded')} "
              f"retired={s.get('retired')}")
        print(f"  {verdict.get('why')}")
    return int(verdict.get("exit") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
