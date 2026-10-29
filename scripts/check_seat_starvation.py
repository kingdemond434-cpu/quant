"""A SEAT PARKED AT ITS QUOTA WITH WORK WAITING IS RED. Reads DEEPENING_THROUGHPUT.json.

WHY (2026-10-29, hourly pass 21). MT5-Deepening ran every hour and logged "seat lane stood down:
0 free request(s) left today of a 519 ceiling" with 146 rows waiting and 0 new candidates. The
task, the producer census and the organ contract all read it as alive, because it was: it was
capped. A cap that holds for more than STARVED_PASSES_RED passes is the brain's real throughput
limit and has to be someone's problem, so this exits 1 and names it.

    python scripts/check_seat_starvation.py            # exit 1 = RED
    python scripts/check_seat_starvation.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
THROUGHPUT = ROOT / "desks" / "mt5" / "reports" / "DEEPENING_THROUGHPUT.json"

#: More than this many consecutive starved passes is RED (principal rule 23: a seat at its quota
#: with backlog for more than 2 passes).
STARVED_PASSES_RED = 2


def verdict(doc: dict[str, Any] | None) -> dict[str, Any]:
    """GREEN, RED or UNMEASURED, with the sentence that says why."""
    if not doc:
        return {"verdict": "UNMEASURED", "why": f"{THROUGHPUT.name} is absent or unreadable"}
    if "seat_starved_passes" not in doc:
        return {"verdict": "UNMEASURED",
                "why": "the worker that wrote this artifact predates the starvation streak"}
    n = int(doc.get("seat_starved_passes") or 0)
    base = {"seat_starved_passes": n, "since": doc.get("seat_starved_since"),
            "backlog": doc.get("backlog_after"), "at": doc.get("at")}
    if n > STARVED_PASSES_RED:
        return {**base, "verdict": "RED",
                "why": (f"the deepening seat stood down at its daily quota for {n} consecutive "
                        f"passes with {doc.get('backlog_after')} row(s) waiting. Owner: the LLM "
                        f"seat budget (free models, waste recovery, per-organ allocation)")}
    return {**base, "verdict": "GREEN", "why": f"{n} starved pass(es), limit {STARVED_PASSES_RED}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        doc = json.loads(THROUGHPUT.read_text("utf-8"))
    except (OSError, ValueError):
        doc = None
    v = verdict(doc if isinstance(doc, dict) else None)
    print(json.dumps(v, indent=1) if args.json else f"{v['verdict']}: {v['why']}")
    return 1 if v["verdict"] == "RED" else 0


if __name__ == "__main__":
    sys.exit(main())
