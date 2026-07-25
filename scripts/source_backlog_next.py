#!/usr/bin/env python3
"""Print the next source(s) to VERIFY this cycle -- clears the existing catalogue, never
generates more.

The bottleneck in the desk's data-hunting pipeline was never generation (prospector/litminer
already catalogue faster than anything gets verified) -- it is verification: reading the actual
docs/ToS and testing the actual endpoint (the Baidu-vs-NAVER distinction this session took real
reading, not a prompt). This script does exactly the mechanical half of that: parse the existing
watchlist, exclude anything already resolved ("if not already in system"), and surface a bounded
batch to work on THIS cycle. The actual verification (read the docs, hit the endpoint, grade it) is
a cycle-level research task, not something this script does for you.

Usage: source_backlog_next.py [--watchlist docs/research/data_axis_watchlist.md] [--limit 3]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from libs.research.source_backlog import backlog_from_file


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--watchlist", default="docs/research/data_axis_watchlist.md")
    # 0 = UNBOUNDED (default, principal 2026-07-25: no throttles on research). Conversion
    # must always maximise and exhaust; a per-cycle cap on how many findings can even be
    # SURFACED throttles the conversion half of the objective before work begins.
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()

    path = Path(a.watchlist)
    if not path.exists():
        print(f"no watchlist at {path} -- nothing to pick from")
        return
    rep = backlog_from_file(path, limit=a.limit)
    print(f"SOURCE BACKLOG: {rep.n_total} catalogued, {rep.n_resolved} resolved (excluded), "
          f"{rep.n_verification_pending} pending verification, "
          f"{rep.n_legitimacy_pending} pending a legitimacy decision")
    print(f"  {rep.verdict}")
    if rep.next_verification:
        print("  VERIFY this cycle (technical check -- docs + endpoint):")
        for name in rep.next_verification:
            print(f"    - {name}")
    if rep.next_legitimacy:
        print("  DECIDE this cycle (policy/legal, not a technical test):")
        for name in rep.next_legitimacy:
            print(f"    - {name}")


if __name__ == "__main__":
    main()
