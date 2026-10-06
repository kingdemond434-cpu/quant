#!/usr/bin/env python3
"""THE PAID-SUBSTITUTE FENCE -- the hunt for free replicas of paid datasets is alive and never
loses ground (principal 2026-09-30: "all paid datasets alternatives ... thousands").

What it asserts, through `research.paid_substitute_engine.fence`:

  * THE CATALOGUE NEVER SHRINKS. The seeded paid-dataset catalogue
    (`desks/mt5/data/paid_dataset_catalogue/`) holds at least the committed floor (`_floor.json`),
    and the report's own recorded catalogue is not below it either.
  * THE REPORT IS FRESH. `desks/mt5/reports/PAID_SUBSTITUTE_COVERAGE.json`, written by the hourly
    leg `paid_substitute_engine`, is no older than six hours (the leg is CORE, but leg rotation
    can skip a healthy leg for an hour; three missed passes is a stopped clock).

A STATE fence, not a law fence: the report lives under `desks/mt5/reports/**`, which git does not
carry, so on a clean checkout it is absent. Without `--require-state` an absent report reads
UNMEASURED and passes (the catalogue floor is still checked, since the catalogue is committed);
with it -- the box, where the leg runs -- an absent report is the failure it names.

It never edits the catalogue, the report or any cell. Exit 0 clean, 1 on a failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--require-state", action="store_true",
                    help="an absent report is a failure (the host where the leg runs)")
    a = ap.parse_args(argv)
    desk = a.root / "desks" / "mt5"
    for p in (str(a.root), str(desk)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from research import paid_substitute_engine as pse

    report = desk / "reports" / "PAID_SUBSTITUTE_COVERAGE.json"
    cat = desk / "data" / "paid_dataset_catalogue"
    fails = pse.fence(report, catalogue_dir=cat, floor_path=cat / "_floor.json",
                      require_report=bool(a.require_state))
    for f in fails:
        print(f"FAIL {f}")
    if not fails and not report.exists():
        print("paid_substitute fence: OK (report UNMEASURED on this host; catalogue floor held)")
        return 0
    print("paid_substitute fence:", "FAIL" if fails else "OK")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
