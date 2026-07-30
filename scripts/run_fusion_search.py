#!/usr/bin/env python3
"""FUSION SEARCH runner -- writes data/fusion_search.json (EXECUTION_QUEUE.md RANK 5).

Combinatorial search over dataset axes, gated so it cannot mine noise. Distinct from
scripts/fusion_engine.py, which transforms known inputs rather than searching.

THE GATE IS THE PRODUCT. An axis enters combination search only after passing its own single-axis
screen; the trial budget is charged on the ENUMERATED grid (a cheap prune saves compute, never
multiplicity); and the grid is hashed before compute so it cannot be grown after results are seen.
See libs/research/fusion_search.py for why an ungated version would return a fake survivor every run.

On this desk today it correctly searches NOTHING: no axis has earned breadth. That refusal, with the
reason per axis, IS the output.

    python scripts/run_fusion_search.py
    python scripts/run_fusion_search.py --axis a=SCREEN-INTERESTING --axis b=SCREEN-INTERESTING
    python scripts/run_fusion_search.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from libs.research.fusion_search import (
    DEFAULT_K,
    eligibility_from_screens,
    plan_search,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/fusion_search.json"

#: Where single-axis screen verdicts land. Read rather than assumed -- an axis is eligible because
#: a screen SAID so, never because this script was told to believe it.
_SCREEN_DIRS = ("reports/axis_screens", "reports")


def _discover_verdicts() -> dict[str, str]:
    """axis -> its STRONGEST single-axis cell verdict.

    Verdicts live per CELL (a screen report is a grid of construction x horizon trials), not at the
    top level, so an axis verdict has to be reduced from its cells. Strongest-of-cells is the right
    reduction and is not free peeking: the axis screen already counted every one of its own cells in
    its own n_trials, so 'one cell showed signal' is a result that has already been paid for. What
    it must NOT do is let that one cell license an unpriced combinatorial expansion -- which is
    exactly what fusion_search's enumeration budget then charges for separately.
    """
    order = ["SCREEN-INTERESTING", "SCREEN-WEAK", "SCREEN-UNDERPOWERED",
             "TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD"]
    rank = {v: i for i, v in enumerate(order)}
    out: dict[str, str] = {}
    for d in _SCREEN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.json")):
            try:
                doc = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict):
                continue
            axis = f.stem.replace("screen_", "")
            cells = doc.get("cells")
            found: list[str] = []
            if isinstance(cells, list):
                found = [str(c["verdict"]) for c in cells
                         if isinstance(c, dict) and isinstance(c.get("verdict"), str)]
            elif isinstance(doc.get("verdict"), str):
                found = [str(doc["verdict"])]
            if found:
                best = min(found, key=lambda v: rank.get(v, len(order)))
                if axis not in out or rank.get(best, 99) < rank.get(out[axis], 99):
                    out[axis] = best
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--axis", action="append", default=[], metavar="NAME=VERDICT",
                    help="declare an axis verdict explicitly (repeatable)")
    ap.add_argument("--k", type=int, default=DEFAULT_K, help=f"combination width (default {DEFAULT_K})")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    verdicts = _discover_verdicts()
    for item in a.axis:
        if "=" not in item:
            print(f"fusion-search: --axis needs NAME=VERDICT, got {item!r}", file=sys.stderr)
            return 2
        name, verdict = item.split("=", 1)
        verdicts[name.strip()] = verdict.strip()

    if not verdicts:
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(), "status": "NO-INPUT",
            "detail": "no single-axis screen verdicts found under reports/ -- combination search "
                      "is gated on axes that have EARNED breadth, so with no screens on disk there "
                      "is nothing eligible. Run the single-axis screens first.",
            "cells": 0, "effective_n_trials": 0,
        }
    else:
        el = eligibility_from_screens(verdicts)
        plan = plan_search(el, k=a.k)
        payload = {
            "generated": datetime.now(tz=UTC).isoformat(),
            "status": "REFUSED" if plan.refused_reason else "PLANNED",
            "detail": plan.refused_reason or
                      f"{len(plan.cells)} cells enumerated; {plan.effective_n_trials} trials owed",
            "k": a.k,
            "grid_hash": plan.grid_hash,
            "cells": len(plan.cells),
            "effective_n_trials": plan.effective_n_trials,
            "eligible": plan.eligible,
            "excluded": [asdict(e) for e in plan.excluded],
            "cell_ids": [c.cell_id for c in plan.cells],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    tmp.replace(OUT)

    if a.json:
        print(json.dumps(payload, indent=1, default=str))
        return 0
    print(f"fusion-search | {payload['status']}")
    print(f"  {payload['detail']}")
    for e in payload.get("excluded", []):
        print(f"  EXCLUDED {e['axis']:<26} {e['reason'][:100]}")
    if payload.get("eligible"):
        print(f"  ELIGIBLE {', '.join(payload['eligible'])}")
    if payload.get("cells"):
        print(f"  grid {payload['grid_hash']} -- {payload['cells']} cells, "
              f"{payload['effective_n_trials']} trials owed BEFORE any pruning")
    print(f"\n-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
