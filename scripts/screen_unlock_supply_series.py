#!/usr/bin/env python3
"""STAGE-A RUNNER: mechanical supply release as a schedule-SERIES (census gap #3, score 0.360).

All pre-registration -- mechanism, constructions, horizons, alignment, multiplicity charge --
lives in the module docstring of `libs/research/unlock_supply_series.py` and was written before
any number was computed.  This file only wires it to disk and writes the artifact; it contains
no thresholds and no analysis, so there is nothing here to tune after seeing a result.

INTENDED CADENCE (header comment only -- ops/crontab.manifest is owned by another pass):
    # 25 6 * * 1   weekly, Monday 06:25 UTC, after the unlock-calendar and circulating-supply
    #              collectors would have landed.  Weekly because the mechanism is a 7-30 day
    #              forward window: a daily re-read would re-test the same overlapping window and
    #              inflate the trial count without adding independent evidence.

    python scripts/screen_unlock_supply_series.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.unlock_supply_series import run_screen  # noqa: E402

_OUT = _ROOT / "reports/axis_screens/unlock_supply_series.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the artifact to stdout")
    args = ap.parse_args()

    report = run_screen(
        schedule_path=_ROOT / "data/unlock_events.json",
        supply_path=_ROOT / "data/circulating_supply.jsonl",
        bars=None,
    )
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"status : {report['status']}")
        print(f"verdict: {report['verdict']}")
        print(f"power  : {report['power']['label']} -- {report['power']['note']}")
        for miss in report.get("missing_inputs", []):
            print(f"MISSING: {miss}")
        print(f"cells declared: {len(report.get('cells_declared', report.get('cells', [])))}")
        print(f"artifact: {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
