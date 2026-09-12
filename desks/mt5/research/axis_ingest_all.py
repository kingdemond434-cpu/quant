"""INGEST EVERY AXIS, EVERY PASS -- and keep one report that shows all of them at once.

THE PRINCIPAL, 2026-09-12: "no make it ingest all there always bro".

WHAT WAS WRONG. `axis_ingest.py` takes `--axis` and runs exactly ONE ingester per invocation,
then writes BOTH a per-axis file and the shared `AXIS_INGEST.json`. The scheduled runner passed
`--axis cot`, so:

  * only one of the four axes was refreshed on the clock, and
  * the shared report carried whichever axis ran LAST -- measured 2026-09-12 it held FRED's
    result (0 series, 7 failed), which reads as "the axis lane is broken" while COT had in fact
    just ingested 4,060 rows across 22 MT5 symbols and BIS 464,803 rows across 33.

A report that shows one lane's worst pass and hides three healthy ones is worse than no report:
it is the shape that makes an operator distrust the board and stop reading it.

WHY A DRIVER AND NOT AN EDIT TO `axis_ingest.py`. The trading box's copy of that file is 438
lines AHEAD of this tree -- it has had work done on it that has not reached here. Editing it from
here would have reverted that work, which is the exact failure the moneypath guard exists to stop
(1,078 lines once vanished from gateway.py this way). So this IMPORTS whatever version is
present and drives its own `INGESTERS` table. New axes added there are picked up here for free,
with no second list to keep in sync.

FAILURE IS PER-AXIS AND NEVER FATAL. FRED currently times out and resets from this box's IP
(7/7). That is a fact about one publisher's edge network, not about the axis lane, and it must
never stop COT, BIS or ECB from refreshing. Each ingester is caught individually and recorded as
UNMEASURED with its error -- a failed fetch is not evidence that an axis is barren (L1.28a).

    python desks/mt5/research/axis_ingest_all.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT_DIR = DESK / "data" / "axes"
REPORT = DESK / "reports" / "AXIS_INGEST.json"


def _count(doc: dict[str, Any]) -> int:
    """Rows for a tabular axis, series for a time-series one. Both are 'how much landed'."""
    for k in ("n_rows", "n_series"):
        v = doc.get(k)
        if isinstance(v, int):
            return v
    return 0


def run_all(apply: bool) -> dict[str, Any]:
    import axis_ingest as ai

    now = datetime.now(tz=UTC)
    axes: dict[str, Any] = {}
    for name in sorted(ai.INGESTERS):
        try:
            doc = ai.INGESTERS[name]()
        except Exception as exc:
            # ONE PUBLISHER'S OUTAGE IS NOT THE LANE'S VERDICT. Recorded, then carry on.
            axes[name] = {"axis": name, "state": "UNMEASURED",
                          "error": f"{type(exc).__name__}: {exc}",
                          "why": ("a failed fetch is not evidence that the axis is barren; the "
                                  "previous per-axis file on disk still stands")}
            continue
        n = _count(doc)
        axes[name] = {
            "axis": name,
            "state": "OK" if n else "EMPTY",
            "n": n,
            "n_symbols": len(doc.get("symbols") or []),
            "n_failed": len(doc.get("failed") or {}),
            "failed": {k: str(v)[:120] for k, v in (doc.get("failed") or {}).items()},
        }
        if apply:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / f"{name}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")

    ok = [k for k, v in axes.items() if v.get("state") == "OK"]
    return {
        "at": now.isoformat(timespec="seconds"),
        "driver": "axis_ingest_all -- every axis, every pass",
        "n_axes": len(axes),
        "n_ok": len(ok),
        "n_unmeasured": sum(1 for v in axes.values() if v.get("state") == "UNMEASURED"),
        "n_empty": sum(1 for v in axes.values() if v.get("state") == "EMPTY"),
        "total_rows": sum(int(v.get("n") or 0) for v in axes.values()),
        "axes": axes,
        "rule": ("every axis runs on every pass and each writes its own file. The shared report "
                 "is a UNION, never the last writer's result -- a board that shows one lane's "
                 "worst pass and hides three healthy ones teaches the reader to stop looking."),
        "boundary": ("ingestion is not conditioning. A row here is a dated series a family COULD "
                     "condition on; whether it earns anything is the gauntlet's verdict."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the per-axis files and the report")
    a = ap.parse_args(argv)
    doc = run_all(a.apply)
    print(f"axis ingest: {doc['n_ok']}/{doc['n_axes']} axis(es) OK, "
          f"{doc['total_rows']:,} row(s) total")
    for name, v in doc["axes"].items():
        if v.get("state") == "UNMEASURED":
            print(f"  {name:<10} UNMEASURED  {str(v.get('error'))[:70]}")
        else:
            extra = f"  ({v['n_failed']} sub-fetch failure(s))" if v.get("n_failed") else ""
            print(f"  {name:<10} {v['state']:<10} n={v['n']:<8} symbols={v['n_symbols']}{extra}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(f"-> {REPORT}")
    # NON-ZERO ONLY IF EVERY AXIS FAILED. One publisher down is a normal day.
    return 0 if doc["n_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
