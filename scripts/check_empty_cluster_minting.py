#!/usr/bin/env python3
"""THE EMPTY-CLUSTER MINTING FENCE: every one of the six target clusters got cells in 24 hours.

    python scripts/check_empty_cluster_minting.py [--json] [--window-h 24]

The principal's standing order (2026-09-30) is to fill cross_asset_lead_lag, event_surprise,
execution_entry, news_reaction, options_implied and positioning_flow. The producer is
`desks/mt5/research/empty_cluster_breadth.py`, hourly; it appends one row per cluster per pass
to `desks/mt5/data/empty_cluster_mint_ledger.jsonl`. This fence reads that ledger and goes RED
when ANY of the six has zero cells minted in the window -- naming, per red cluster, the input the
producer last reported missing, so the red carries its remedy.

An absent ledger is UNMEASURED, and UNMEASURED is RED here: the order is that cells are minted,
and a producer that has never run has minted none (L1.28a -- absence is not a clean verdict).

Writes `desks/mt5/reports/EMPTY_CLUSTER_MINTING.json`. Exit 1 on RED, 0 on GREEN.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = DESK / "reports" / "EMPTY_CLUSTER_MINTING.json"


def check(window_h: float = 24.0, ledger: Path | None = None) -> dict:
    from research.empty_cluster_breadth import CLUSTERS, minted_in_window
    win = minted_in_window(hours=window_h, ledger=ledger)
    red = list(CLUSTERS) if win.get("status") != "MEASURED" else list(win["zero_minted"])
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "fence": "scripts/check_empty_cluster_minting.py",
            "verdict": "RED" if red else "GREEN", "window_h": window_h,
            "red_clusters": red, "measurement": win,
            "rule": ("RED when any of the six target clusters has zero cells minted in the "
                     "window; an absent ledger is UNMEASURED and RED")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window-h", type=float, default=24.0)
    args = ap.parse_args(argv)
    doc = check(args.window_h)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    if args.json:
        print(json.dumps(doc, indent=1))
    else:
        print(f"empty-cluster minting: {doc['verdict']} (window {args.window_h:g}h)")
        m = doc["measurement"]
        if m.get("status") != "MEASURED":
            print(f"  UNMEASURED: {m.get('why')}")
        for c in doc["red_clusters"]:
            miss = (m.get("last_missing_inputs") or {}).get(c) or []
            print(f"  RED {c:22} 0 minted" + (f"  missing: {', '.join(miss[:3])}" if miss else ""))
    return 1 if doc["red_clusters"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
