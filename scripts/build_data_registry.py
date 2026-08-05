#!/usr/bin/env python3
"""DATA ASSET REGISTRY builder -- writes data/data_assets.json (EXECUTION_QUEUE.md RANK 4).

Closes GAP_REGISTER row #77: the previous inventory was hand-written, reported ROW COUNTS as SPANS
(``liquidations.parquet`` "33,867 rows" is really 17 days / 15 symbols) and omitted the desk's best
panel entirely (``data/lake/bronze/crypto/<SYM>/D1`` -- 267 symbols, daily, from 2019-09-08),
so organs were choosing what to test off a map that was wrong in both directions.

Every number here is MEASURED from the data or explicitly absent. See
``libs/research/data_registry.py`` for why moat and research value are scored separately.

2026-08-05 -- SPANS NOW CARRY THEIR HOLES, AND THEIR ABSENCE CARRIES AN ADDRESS. Two additions,
both for the same reason: ``t = SR*sqrt(years)`` is the only lever the power audit found moves
power at all, so the span an organ reads here directly sizes a t-stat.

  * ELAPSED IS NOT EVIDENCE. Every measured span now reports ``observed_days``, its gap runs and
    ``evidence_years``. The desk's own BTCUSDT daily cache spans 2069 days and is missing all of
    2025-10; quoting 5.66 years for it is the same overstatement class as row #77's row-counts.
  * ABSENT IS NOT ZERO, AND IT HAS A PATH. A declared asset that cannot be opened on this box reads
    NOT-READABLE-HERE with the exact missing path, never 0 and never a guess. The same script run
    on the VPS completes exactly those rows, which is why it bootstraps its own sys.path and takes
    ``--root``.

    python scripts/build_data_registry.py            # sampled spans for partitioned trees (fast)
    python scripts/build_data_registry.py --deep     # measure every partition member
    python scripts/build_data_registry.py --json     # machine output on stdout
    python scripts/build_data_registry.py --root /home/quant/quant-platform   # measure another box
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# VPS-runnable: `.venv/bin/python scripts/build_data_registry.py` must import libs/ without the
# caller having exported PYTHONPATH. The live box's root is tried first so a copy of this file run
# from anywhere on it still measures the real desk (the house pattern, scripts/run_type2_report.py).
_VPS_ROOT = Path("/home/quant/quant-platform")
ROOT = _VPS_ROOT if (_VPS_ROOT / "libs/research/data_registry.py").exists() \
    else Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.data_registry import (  # noqa: E402
    NOT_READABLE_HERE,
    REPL_PROPRIETARY,
    DataAsset,
    build,
)


def _span_cell(a: DataAsset) -> str:
    sp = a.span
    if not sp.measured or not sp.days:
        return f"[{NOT_READABLE_HERE if not sp.readable_here else sp.status}]"
    cell = f"{sp.first}->{sp.last} ({sp.days}d"
    if sp.gap_days:
        cell += f" -{sp.gap_days}d gap"
    return cell + ")"


def _fmt(a: DataAsset) -> str:
    return (f"  {a.id:<28} {_span_cell(a):<44} breadth={a.breadth or '-':<5} "
            f"moat={a.moat_score:<5} value={a.research_value:<5} "
            f"cad={f'{a.cadence_h}h' if a.cadence_h else 'UNSCHEDULED'}")


def _span_json(a: DataAsset) -> dict[str, object]:
    """The depth question -- 'which source is long enough to test anything on' -- in one row."""
    sp = a.span
    return {"id": a.id, "path": a.path, "years": sp.years, "evidence_years": sp.evidence_years,
            "days": sp.days, "observed_days": sp.observed_days, "gap_days": sp.gap_days,
            "n_gaps": sp.n_gaps, "largest_gap_days": sp.largest_gap_days,
            "largest_gap_from": sp.largest_gap_from, "largest_gap_to": sp.largest_gap_to,
            "balanced_days": sp.balanced_days, "rows": a.rows, "breadth": a.breadth,
            "first": sp.first, "last": sp.last}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep", action="store_true",
                    help="measure every partition member instead of sampling")
    ap.add_argument("--json", action="store_true", help="emit the registry on stdout")
    ap.add_argument("--root", default=None,
                    help="measure a different checkout (the VPS completes what a dev box cannot)")
    a = ap.parse_args(argv)

    root = Path(a.root).resolve() if a.root else ROOT
    out = root / "data/data_assets.json"

    assets = build(root, deep=a.deep)
    measured = [x for x in assets if x.span.measured]
    absent = [x for x in assets if x.span.status == "absent"]
    gapped = [x for x in measured if x.span.gapped]
    unread = [x for x in assets if (x.span.days or 0) > 365 and not x.consumers]
    unscheduled = [x for x in assets if x.collector and x.cadence_h is None]
    by_evidence = sorted(measured, key=lambda x: -(x.span.evidence_years or 0.0))

    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "deep": a.deep,
        "root": root.as_posix(),
        "counts": {"assets": len(assets), "measured": len(measured), "absent": len(absent),
                   # same set as `absent`, named the way the rest of the desk names it
                   "not_readable_here": len(absent), "gapped": len(gapped)},
        # THE row-#77 headline: spans are the map organs navigate by, so report the real extremes
        "longest_span_days": max((x.span.days or 0 for x in measured), default=0),
        # ...and the 2026-08-05 addition: the same extreme with its holes subtracted. The pair is
        # the point -- where they differ, the difference is history the desk does not actually have.
        "longest_evidence_days": max((x.span.observed_days or 0 for x in measured), default=0),
        "longest_evidence_years": max((x.span.evidence_years or 0.0 for x in measured), default=0.0),
        "widest_breadth": max((x.breadth or 0 for x in assets), default=0),
        "proprietary": [x.id for x in assets if x.replication == REPL_PROPRIETARY],
        "unread_long_history": [x.id for x in unread],
        "unscheduled_collectors": [x.id for x in unscheduled],
        # every measured asset ranked by the term that sizes a t-stat, deepest first
        "spans": [_span_json(x) for x in by_evidence],
        "gapped": [{"id": x.id, "gap_days": x.span.gap_days, "n_gaps": x.span.n_gaps,
                    "largest_gap_days": x.span.largest_gap_days,
                    "largest_gap_from": x.span.largest_gap_from,
                    "largest_gap_to": x.span.largest_gap_to,
                    "years": x.span.years, "evidence_years": x.span.evidence_years}
                   for x in gapped],
        # NEVER a count on its own: an operator must be able to read which path was missing
        "not_readable_here": [{"id": x.id, "missing_path": x.span.missing_path or x.path,
                               "collector": x.collector, "status": NOT_READABLE_HERE}
                              for x in absent],
        "assets": [x.to_json() for x in assets],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), "utf-8")
    tmp.replace(out)                     # atomic: a torn registry is a misleading map again

    if a.json:
        print(json.dumps(payload, indent=1))
        return 0

    print(f"data-registry | {len(assets)} assets, {len(measured)} with MEASURED spans, "
          f"{len(absent)} {NOT_READABLE_HERE} on this box")
    for x in assets:
        print(_fmt(x))

    if by_evidence:
        print("\n  DEPTH (t = SR*sqrt(years), so this is the column that sizes every test):")
        for x in by_evidence[:8]:
            sp = x.span
            claim = f"{sp.years}y elapsed"
            honest = f"{sp.evidence_years}y observed" if sp.evidence_years is not None \
                else "gaps UNMEASURED (sampled)"
            print(f"    {x.id:<26} {claim:<16} -> {honest}"
                  + (f"  [{sp.n_gaps} gap(s), largest {sp.largest_gap_days}d "
                     f"{sp.largest_gap_from}..{sp.largest_gap_to}]" if sp.gapped else ""))
    if gapped:
        print(f"\n  INTERNAL GAPS: {len(gapped)} measured asset(s) have holes. An elapsed span is "
              f"not evidence over its holes -- use evidence_years, not years.")
    if unread:
        # row #77's second defect: cot_zcache is 26 YEARS of CFTC COT and nothing read it
        print(f"\n  PARALYSIS: {len(unread)} asset(s) with >1y history and NO reader -- "
              f"{', '.join(x.id for x in unread)}")
        print("  Long history nobody queries is paid-for capability sitting idle (L2.9).")
    if unscheduled:
        print(f"\n  UNSCHEDULED: {len(unscheduled)} collector(s) write an asset on no cadence -- "
              f"{', '.join(x.id for x in unscheduled)}")
    if absent:
        print(f"\n  {NOT_READABLE_HERE} ({len(absent)}), each with the path that was missing:")
        for x in absent[:12]:
            print(f"    {x.id:<28} {x.span.missing_path or x.path}")
        if len(absent) > 12:
            print(f"    ... and {len(absent) - 12} more (all in the artifact's "
                  f"not_readable_here[])")
        print("  Spans are UNMEASURED, not zero -- this box may not be the collecting box.")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
