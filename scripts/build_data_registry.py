#!/usr/bin/env python3
"""DATA ASSET REGISTRY builder -- writes data/data_assets.json (EXECUTION_QUEUE.md RANK 4).

Closes GAP_REGISTER row #77: the previous inventory was hand-written, reported ROW COUNTS as SPANS
(``liquidations.parquet`` "33,867 rows" is really 17 days / 15 symbols) and omitted the desk's best
panel entirely (``data/lake/bronze/crypto/<SYM>/D1`` -- 267 symbols, daily, from 2019-09-08),
so organs were choosing what to test off a map that was wrong in both directions.

Every number here is MEASURED from the data or explicitly absent. See
``libs/research/data_registry.py`` for why moat and research value are scored separately.

    python scripts/build_data_registry.py            # sampled spans for partitioned trees (fast)
    python scripts/build_data_registry.py --deep     # measure every partition member
    python scripts/build_data_registry.py --json     # machine output on stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.research.data_registry import REPL_PROPRIETARY, DataAsset, build

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/data_assets.json"


def _fmt(a: DataAsset) -> str:
    sp = a.span
    span = (f"{sp.first}->{sp.last} ({sp.days}d)" if sp.measured and sp.days
            else f"[{sp.status}]")
    return (f"  {a.id:<28} {span:<32} breadth={a.breadth or '-':<5} "
            f"moat={a.moat_score:<5} value={a.research_value:<5} "
            f"cad={f'{a.cadence_h}h' if a.cadence_h else 'UNSCHEDULED'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep", action="store_true",
                    help="measure every partition member instead of sampling")
    ap.add_argument("--json", action="store_true", help="emit the registry on stdout")
    a = ap.parse_args(argv)

    assets = build(ROOT, deep=a.deep)
    measured = [x for x in assets if x.span.measured]
    absent = [x for x in assets if x.span.status == "absent"]
    unread = [x for x in assets if (x.span.days or 0) > 365 and not x.consumers]
    unscheduled = [x for x in assets if x.collector and x.cadence_h is None]

    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "deep": a.deep,
        "counts": {"assets": len(assets), "measured": len(measured), "absent": len(absent)},
        # THE row-#77 headline: spans are the map organs navigate by, so report the real extremes
        "longest_span_days": max((x.span.days or 0 for x in measured), default=0),
        "widest_breadth": max((x.breadth or 0 for x in assets), default=0),
        "proprietary": [x.id for x in assets if x.replication == REPL_PROPRIETARY],
        "unread_long_history": [x.id for x in unread],
        "unscheduled_collectors": [x.id for x in unscheduled],
        "assets": [x.to_json() for x in assets],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), "utf-8")
    tmp.replace(OUT)                     # atomic: a torn registry is a misleading map again

    if a.json:
        print(json.dumps(payload, indent=1))
        return 0

    print(f"data-registry | {len(assets)} assets, {len(measured)} with MEASURED spans, "
          f"{len(absent)} declared-but-absent on this box")
    for x in assets:
        print(_fmt(x))
    if unread:
        # row #77's second defect: cot_zcache is 26 YEARS of CFTC COT and nothing read it
        print(f"\n  PARALYSIS: {len(unread)} asset(s) with >1y history and NO reader -- "
              f"{', '.join(x.id for x in unread)}")
        print("  Long history nobody queries is paid-for capability sitting idle (L2.9).")
    if unscheduled:
        print(f"\n  UNSCHEDULED: {len(unscheduled)} collector(s) write an asset on no cadence -- "
              f"{', '.join(x.id for x in unscheduled)}")
    if absent:
        print(f"\n  ABSENT HERE: {', '.join(x.id for x in absent)}")
        print("  Spans are UNMEASURED, not zero -- this box may not be the collecting box.")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
