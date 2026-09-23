#!/usr/bin/env python
"""THROUGHPUT IS A RATCHET: it goes up, never down. This fence is what makes that true.

Exits 1 when a measured stage has fallen more than `throughput.REGRESSION_TOLERANCE` below its
own high-water mark. The mark is kept in `desks/mt5/reports/THROUGHPUT.json` and is never
lowered -- so a change that costs the desk a factor of two on any stage of the mint-to-judge
chain fails the law gate instead of quietly costing it a decimal place.

WHY A FENCE AND NOT A NOTE. The defect this lane was opened on -- a write door doing a full
table scan on every write, at four rows a second -- had been live long enough to set the desk's
whole mint rate, and it broke NOTHING. Every row landed. Every gate passed. A ceiling is
invisible precisely because it is not a failure, so it needs a test that fails on its behalf.

THIS IS NOT A CAP AND CANNOT BECOME ONE. It never slows, defers, throttles or refuses a row; it
reads a report and compares two numbers. An UNMEASURED stage is reported as UNMEASURED and is
never treated as a zero (L1.28a).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "desks" / "mt5" / "reports" / "THROUGHPUT.json"


def check(report: Path = REPORT) -> tuple[int, str]:
    if not report.exists():
        return 0, (f"UNMEASURED: {report.relative_to(ROOT).as_posix()} has not been written yet. "
                   "The hourly organ desks/mt5/research/throughput_ledger.py publishes it; an "
                   "absent report is a verdict, not a regression, so this does not fail.")
    try:
        doc = json.loads(report.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return 1, f"FAIL: {report} is unreadable ({type(exc).__name__}: {exc})"
    regs = doc.get("regressions") or []
    marks = doc.get("high_water_rows_per_s") or {}
    lines = [f"high-water rows/s: {json.dumps(marks, sort_keys=True)}",
             f"binding stage: {doc.get('binding_stage')} at "
             f"{doc.get('chain_rows_per_day')} rows/day",
             f"target {doc.get('target_cells_per_day')}/day: {doc.get('target_verdict')}"
             + (f" (short by {doc.get('shortfall_factor')}x)"
                if doc.get("shortfall_factor") else ""),
             f"unmeasured stages: {doc.get('unmeasured_stages')}"]
    if not regs:
        return 0, "OK: no stage has fallen below its high-water mark.\n" + "\n".join(lines)
    detail = "\n".join(
        f"  {r.get('stage')}: {r.get('measured_rows_per_s')} rows/s against a mark of "
        f"{r.get('high_water_rows_per_s')} -- {r.get('factor')}x slower" for r in regs)
    return 1, ("FAIL: throughput regressed on "
               f"{len(regs)} stage(s); throughput only goes up.\n{detail}\n" + "\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, default=REPORT)
    args = ap.parse_args()
    code, msg = check(args.report)
    print(msg, flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
