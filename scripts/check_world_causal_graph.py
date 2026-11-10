#!/usr/bin/env python3
"""THE CAUSAL-GRAPH FENCE -- an organ that is fed and admits nothing must say so in red.

`research/world_causal_graph.py` measures candidate edges every hour and hands the state builder
the admitted ones as conditioning hints. Measured 2026-09-08 and unchanged on 2026-11-10: 0 of 96
measured edges admitted, on 33 of the universe's instruments, and nothing anywhere was red --
the organ ran, wrote, and reported non-zero counts. This fence reads the organ's own
`zero_admission` block and fails when:

  * the verdict is RED: more than `red_after` consecutive passes measured edges while the graph
    holds none admitted (inputs flow, nothing comes out);
  * with `--require-state` (the box, where the leg is scheduled): the report is absent, has no
    `zero_admission` block, or is older than STALE_H -- the leg stopped.

IT LOWERS NOTHING. The admission rule lives in `libs/research/causal_graph.py` and is not read
here, let alone changed: red asks a person to tell "the candidates carry no lead-lag at this
clock" from "an input is not arriving" (the report's `candidate_sources`, `cross_asset_basis`
and `nearest` say which), and the only ways to green are an admitted edge or a repaired input.

UNMEASURED IS A VERDICT (L1.28a): on a clean checkout there is no report, and this exits 0
saying so. It caps nothing and gates no capital (GROWTH_GOVERNANCE Rule 1).

    python scripts/check_world_causal_graph.py [--require-state] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "desks" / "mt5" / "reports" / "WORLD_CAUSAL_GRAPH.json"
#: The leg is hourly; three hours is the same grace the other hourly-report fences give.
STALE_H = 3.0


def _age_h(stamp: Any, now: datetime) -> float | None:
    try:
        at = datetime.fromisoformat(str(stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return (now - at).total_seconds() / 3600.0


def judge(report: Any, *, require_state: bool, now: datetime | None = None) -> dict[str, Any]:
    """{verdict: PASS | FAIL | UNMEASURED, why, ...} for one report document (None = absent)."""
    now = now or datetime.now(tz=UTC)
    if not isinstance(report, dict):
        return {"verdict": "FAIL" if require_state else "UNMEASURED",
                "why": f"{REPORT.name} is absent or unreadable: the causal_graph leg has not "
                       "run on this host"}
    block = report.get("zero_admission")
    age = _age_h(report.get("generated_at"), now)
    out: dict[str, Any] = {"age_h": None if age is None else round(age, 2),
                           "zero_admission": block if isinstance(block, dict) else None}
    if require_state and (age is None or age > STALE_H):
        return {**out, "verdict": "FAIL",
                "why": f"{REPORT.name} is {'undated' if age is None else f'{age:.1f}h old'} "
                       f"(> {STALE_H}h): the causal_graph leg stopped"}
    if not isinstance(block, dict):
        return {**out, "verdict": "FAIL" if require_state else "UNMEASURED",
                "why": "the report carries no zero_admission block (written by an older organ)"}
    if block.get("verdict") == "RED":
        return {**out, "verdict": "FAIL",
                "why": f"RED: {block.get('why') or 'inputs flow and no edge is admitted'}"}
    return {**out, "verdict": "PASS",
            "why": f"zero_admission {block.get('verdict')} (runs={block.get('runs')}, "
                   f"admitted_total={block.get('admitted_total')})"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--require-state", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    res = judge(report, require_state=a.require_state)
    if a.json:
        print(json.dumps(res, indent=1, default=str))
    else:
        print(f"world causal graph fence: {res['verdict']} -- {res['why']}")
    return 1 if res["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
