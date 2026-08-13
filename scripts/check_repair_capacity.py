"""REPAIR-CAPACITY FENCE -- the service rate behind the queue (R0330, L1.28b / L1.0 / L2.0).

check_conversion measures the QUEUE and this measures the CAPACITY that drains it. L1.28b was
derived from an arrival-vs-service comparison, and until now the desk published only arrivals,
dispositions and backlog length -- the queue's length says nothing about whether repair capacity
is improving, because a long queue is equally consistent with fast repair under heavy arrival and
slow repair under light arrival.

WHAT IT PUBLISHES, and why each is separate:
  * mttr_days     -- Kaplan-Meier median time-in-backlog, censoring-aware. The naive completed-only
                     median is published beside it precisely so the gap stays visible.
  * p_fix         -- P(a raised row is IMPLEMENTED within the horizon). The ratchet metric.
  * p_disposed    -- P(a raised row leaves the backlog at all), rejections included. Higher than
                     p_fix by construction; publishing only this one would let the desk raise its
                     apparent repair rate by rejecting more.
  * stock_growth  -- net rows added per ACTIVE ledger day.

REFUSALS ARE FIRST-CLASS. Fewer than MIN_EVENTS completed observations reads INSUFFICIENT; an
unreadable or empty ledger reads UNMEASURED. Neither is a pass and neither is reported as zero,
because a zero here would install a zero floor -- a ratchet that permits anything (L1.28a).

THIS FENCE MEASURES AND NOTHING ELSE. It promotes nothing, sizes nothing and gates no capital. It
cannot make a failing thing pass: the only status that exits non-zero is a REGRESSION against a
floor the desk itself recorded.

    python scripts/check_repair_capacity.py [--json] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.repair_capacity import measure  # noqa: E402

_LEDGER = "docs/research/recommendation_ledger.json"
_OUT = "data/repair_metrics.json"

#: INSUFFICIENT and UNMEASURED pass the FENCE while failing to be a measurement: the fence's job is
#: to fail on a REGRESSION, and refusing to grade a thin sample is correct behaviour, not a breach.
#: The unmeasured state is what check_ratchets fails on, which is where it belongs (L1.0).
_PASSING = frozenset({"MEASURED", "INSUFFICIENT", "UNMEASURED"})


def build_report(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    path = root / _LEDGER
    try:
        doc = json.loads(path.read_text("utf-8"))
        rows = doc.get("recommendations", []) if isinstance(doc, dict) else []
    except (OSError, json.JSONDecodeError) as exc:
        # ABSENT and UNREADABLE stay distinct from "measured zero" (L1.55): a missing ledger and a
        # ledger with nothing owed demand opposite responses.
        return {"generated": now.isoformat(), "status": "UNMEASURED",
                "law": "L1.28b -- repair capacity is the service rate behind the queue",
                "detail": f"ledger unreadable ({exc.__class__.__name__}) -- UNMEASURED, not zero",
                "n_rows": 0}

    cap = measure(rows, now=now)
    return {
        "generated": now.isoformat(),
        "law": "L1.28b -- repair capacity is the service rate behind the queue",
        "ledger": _LEDGER,
        **cap.as_dict(),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    rep = build_report(_ROOT)
    out = _ROOT / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"repair capacity: {rep['status']} -- {rep.get('detail', '')}")
        if rep.get("status") == "MEASURED":
            print(f"  MTTR (KM median)   {rep['mttr_days']} d"
                  f"   [naive completed-only {rep['mttr_naive_days']} d]")
            print(f"  p75                {rep['mttr_p75_days'] or 'NOT-REACHED'}")
            print(f"  P(fix | eligible)  {rep['p_fix']}"
                  f"   P(disposed) {rep['p_disposed']}")
            print(f"  stock growth       {rep['stock_growth_per_active_day']:+} rows/active day")
            print(f"  denominators       {rep['n_events']} completed, {rep['n_censored']} censored,"
                  f" {rep['n_active_days']} active days ({rep['n_idle_days']} idle),"
                  f" {rep['n_negative_latency']} negative-latency rows excluded")

    if args.report_only:
        return 0
    # Subject to L1.57: the denominator is the rows this run actually parsed, so an empty or
    # unreadable ledger refuses its own pass instead of reporting a clean board.
    return fence_exit(rep["status"], _PASSING, scanned=int(rep.get("n_rows") or 0),
                      of="docs/research/recommendation_ledger.json rows",
                      fence="check_repair_capacity.py")


if __name__ == "__main__":
    raise SystemExit(main())
