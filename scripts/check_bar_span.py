#!/usr/bin/env python3
"""BAR SPAN FENCE (L1.68) -- does a bar cover the market time its label claims?

L1.46 fenced WHEN a bar is stamped. Nothing asked HOW MUCH MARKET TIME IT HOLDS, and a "D1" label
claims both. Measured over this desk's own primary universe: 68 MT5 D1 series, 42 carrying bars on
days the calendar declares closed, 7,033 such bars, worst 9.16% (EURILS). They are genuine
one-to-three-hour Sunday-open stubs -- 100% are EXTRA sixth bars at ~0.5% of weekday volume -- so
they are never deleted; they are declared and excluded at the point of consumption.

The desk had written the rule down twice and enforced it never: ``libs/data/calendar.is_open`` has
zero callers, ``InstrumentSpec.trades_weekends`` has zero non-test readers, and the one
completeness check computes ``expected.difference(present)`` -- the MISSING direction only.

WHAT IT COSTS: annualised vol understated up to 4.95% (which OVERSIZES the contaminated symbols
under inverse-vol weighting) and lag-1 autocorrelation inflated 34% on EURILS, manufacturing
apparent mean-reversion out of an instrument artifact.

  OK                (exit 0) -- every measured series is inside its session calendar.
  DECLARED          (exit 0) -- contamination exists, all at or below floor, published per symbol.
  CONTAMINATED      (exit 2) -- a share rose above its floor, or is contaminated with no floor.
  UNMEASURED        (exit 2) -- nothing scanned. Never OK (L1.28a).
  NOT-READABLE-HERE (exit 0) -- gitignored VPS-only lake unreadable here. Never OK-by-default.

THE FLOOR RATCHETS DOWNWARD ONLY (L1.0) and `--record` is an EXPLICIT act, never automatic: a
fence that re-baselines itself on every run accepts each regression as the new normal, which is a
gate welded open (L1.63). The gap between today's floors and zero is the work queue.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.bar_span import (  # noqa: E402
    MT5_CLASSES,
    PASSING,
    load_floors,
    ratchet_floors,
    scan_lake,
)

_OUT = _ROOT / "data/bar_span.json"
_FLOORS = _ROOT / "data/bar_span_floors.json"


def _render(rep: dict[str, object]) -> str:
    lines = [
        f"BAR SPAN (L1.68): {rep['status']}  "
        f"series={rep['n_series']} attempted={rep['n_attempted']} skipped={rep['n_skipped']}",
        f"  contaminated={rep['n_contaminated']} clean={rep['n_clean']}  "
        f"out-of-calendar bars={rep['n_out_of_calendar_bars']} / {rep['n_bars']}",
        f"  by kind: {rep['by_kind']}",
    ]
    if rep["anomalous"]:
        lines.append(
            f"  ANOMALOUS (full-size bars on a shut market -- repair the INGEST, not the read): "
            f"{', '.join(rep['anomalous'])}"  # type: ignore[arg-type]
        )
    rows = [r for r in rep["series"] if r["n_out_of_calendar"]]  # type: ignore[union-attr,index]
    for r in rows[:12]:
        floor = "unrecorded" if r["floor"] is None else f"{r['floor']:.4%}"
        lines.append(
            f"    {r['status']:12s} {r['symbol']:9s} {r['n_out_of_calendar']:5d}/{r['n_bars']:<6d}"
            f" = {r['share']:.4%}   {r['kind']:12s} floor={floor}"
        )
    if len(rows) > 12:
        lines.append(f"    ... and {len(rows) - 12} more (full list in the artifact)")
    for s in rep["skips"][:5]:  # type: ignore[union-attr,index]
        lines.append(f"    SKIP {s['symbol']} ({s['asset_class']}): {s['reason']}")
    return "\n".join(lines)


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument(
        "--record",
        action="store_true",
        help="move the per-symbol floors DOWNWARD to today's measurement (explicit act)",
    )
    ap.add_argument("--lake", default=None, help="explicit lake root; defaults to data/lake")
    args = ap.parse_args()

    lake = Path(args.lake) if args.lake else _ROOT / "data/lake"
    floors = load_floors(_FLOORS)
    report = scan_lake(lake, classes=MT5_CLASSES, floors=floors)
    doc = report.as_dict()

    if args.record and report.series:
        moved = ratchet_floors(floors, report)
        _FLOORS.parent.mkdir(parents=True, exist_ok=True)
        _FLOORS.write_text(
            json.dumps(
                {
                    "law": "L1.68",
                    "_": "Per-symbol out-of-calendar share. RATCHETS DOWNWARD ONLY (L1.0): a "
                    "repair is permanent; a regression is never re-baselined into acceptance. "
                    "The gap to zero is the work queue, not an accepted state.",
                    "floors": {k: round(v, 6) for k, v in sorted(moved.items())},
                },
                indent=1,
            )
            + "\n",
            "utf-8",
        )
        # Re-derive against the floors just written so the artifact and the exit code agree.
        report = scan_lake(lake, classes=MT5_CLASSES, floors=moved)
        doc = report.as_dict()

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")

    print(json.dumps(doc, indent=1) if args.json else _render(doc))
    if args.report_only:
        return 0
    return fence_exit(
        doc["status"], PASSING, scanned=doc["n_series"], of="MT5 D1 lake series", fence="bar_span"
    )


if __name__ == "__main__":
    raise SystemExit(main())
