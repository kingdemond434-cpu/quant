#!/usr/bin/env python3
"""Standalone hourly fallback for the 12-miner discovery suite (principal 2026-08-25).

The hourly controller's Phase 1 already runs every miner and converts discoveries to
hypotheses each hour -- but the controller itself died twice on 2026-08-25 (import breakage)
and the miners died with it, silently. This wrapper decouples survival: if NO fresh discovery
artifact exists within STALE_MIN, it runs the suite standalone and converts, exactly as the
controller would. If the controller is healthy it exits without touching anything, so sources
are never double-scraped (a banned scraper is a dead discovery channel -- source burn is
discovery loss).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/home/quant/quant-platform")
INTEL = ROOT / "data" / "intelligence"
SIDE = ROOT / "desks" / "mt5" / "side_channels"
STALE_MIN = 70


def newest_discovery_age_min() -> float | None:
    newest = None
    for p in INTEL.rglob("discoveries_*.json"):
        m = p.stat().st_mtime
        newest = m if newest is None else max(newest, m)
    if newest is None:
        return None
    return (time.time() - newest) / 60


def main() -> int:
    age = newest_discovery_age_min()
    if age is not None and age < STALE_MIN:
        print(f"miners fresh ({age:.0f}min old) -- controller healthy, standing down")
        return 0
    print(f"discoveries stale ({'never' if age is None else f'{age:.0f}min'}) -- "
          f"controller presumed down; running suite standalone")
    sys.path.insert(0, str(SIDE))
    from run_all_miners import run_all_miners            # noqa: PLC0415
    results = run_all_miners()
    summary = results.get("summary", {})
    try:
        from convert_to_hypotheses import convert_discoveries  # noqa: PLC0415
        hyp = convert_discoveries()
        out = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "latest_external.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(hyp, indent=2, default=str), "utf-8")
        print(f"fallback: {summary.get('total_discoveries', 0)} discoveries from "
              f"{summary.get('successful_miners', 0)} miners; hypotheses written "
              f"at {datetime.now(tz=UTC).isoformat(timespec='seconds')}")
    except Exception as exc:                                             # noqa: BLE001
        print(f"fallback: miners ran, hypothesis conversion failed ({exc}) -- "
              f"discoveries are on disk for the next converter pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
