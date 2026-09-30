#!/usr/bin/env python3
"""Publish the control room: every traded instrument's regime now, and the sleeves it touches.

    python desks/mt5/research/control_room.py [--out PATH]

Writes `desks/mt5/reports/CONTROL_ROOM.json`. The instruments are the union of the regime
contract's core set and every symbol a LIVE or STANDBY sleeve trades, so a sleeve the promoter
adds tomorrow is read tomorrow without an edit here. Each LIVE sleeve is listed under its
instrument's state so the operator sees, in one file, which of the live book is trading into a
trend, a range, high volatility or thin liquidity. It sizes nothing; the allocator reads the same
labels through `libs.regime.control_room.sleeve_weights` once the contract admits it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.regime import control_room as cr  # noqa: E402

BASE = ROOT / "desks" / "mt5"
OUT = BASE / "reports" / "CONTROL_ROOM.json"
SLEEVES = BASE / "data" / "sleeves.json"
CORE = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY",
        "GBPJPY", "AUDJPY", "XAUUSD", "XAGUSD")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    rows = []
    if SLEEVES.exists():
        rows = [r for r in (json.loads(SLEEVES.read_text(encoding="utf-8")).get("sleeves") or [])
                if isinstance(r, dict) and r.get("status") in ("LIVE", "STANDBY")]
    syms = sorted(set(CORE) | {str(r.get("symbol")) for r in rows if r.get("symbol")})
    snap = cr.snapshot(syms)
    by_state: dict[str, list[str]] = {}
    for r in rows:
        if r.get("status") != "LIVE":
            continue
        st = (snap["assets"].get(str(r.get("symbol"))) or {}).get("state") or "UNMEASURED"
        by_state.setdefault(st, []).append(str(r.get("name")))
    doc = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"), **snap,
           "live_sleeves_by_state": by_state,
           "axes": {"vol": "20d realised vol, tercile of own trailing year",
                    "trend": "20d efficiency ratio vs own trailing-year median",
                    "liq": f"spread >= {cr.THIN_SPREAD_MULT}x its 60d median or activity in "
                           f"bottom {cr.QUIET_PCT:.0%} of own year"}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    print(json.dumps({"assets": len(snap["assets"]), "unmeasured": len(snap["unmeasured"]),
                      "share_trending": snap["share_trending"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
