#!/usr/bin/env python3
"""STAGE-A RUNNER: scheduled-event information diffusion (census gap #6, score 0.315).

All pre-registration -- mechanism, constructions, intervals, the exact instant-vs-date alignment
rule, and the multiplicity charge -- lives in the module docstring of
`libs/research/announcement_diffusion.py` and was written before any number was computed.  This
file only wires it to disk and writes the artifact.

INTENDED CADENCE (header comment only -- ops/crontab.manifest is owned by another pass):
    # 40 6 * * *   daily, 06:40 UTC, after scripts/collect_announcements.py.  Daily because the
    #              binding constraint is EVENT ACCUMULATION: the screen refuses to read until
    #              >= 20 instant-bearing announcements land on a symbol that has sub-daily bars,
    #              so the useful output of most runs is the recoverability audit, not a verdict.

    python scripts/screen_announcement_diffusion.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.announcement_diffusion import run_screen  # noqa: E402

_OUT = _ROOT / "reports/axis_screens/announcement_diffusion.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the artifact to stdout")
    args = ap.parse_args()

    report = run_screen(
        announcements_path=_ROOT / "data/exchange_announcements.jsonl",
        bar_root=_ROOT / "data/binance_vision",
    )
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"status : {report['status']}")
        print(f"verdict: {report['verdict']}")
        print(f"instant recoverable: {report.get('instant_recoverable')}")
        audit = report.get("instant_audit")
        if audit is not None:
            print(
                f"instants: {audit['n_instant_recovered']}/{audit['n_rows']} recovered, "
                f"{audit['n_refused']} refused (min precision {audit['min_precision_accepted']})"
            )
            for src, counts in sorted(audit["by_source"].items()):
                print(f"  {src:18s} {counts}")
        print(f"power  : {report['power']['label']} -- {report['power']['note']}")
        for miss in report.get("missing_inputs", []):
            print(f"MISSING: {miss}")
        print(f"artifact: {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
