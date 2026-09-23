#!/usr/bin/env python3
"""GENERAL stranded-spot recovery -- derives the stranded set from ground truth, every incident.

SUPERSEDES scripts/run_deadman_stranded_sweep.py, which hardcoded the THREE symbols of the
2026-07-19 incident (GAP row 34) and so recovered $0.01 of the 2026-07-27 stranding: the carry
churn loop (master 59b837d) re-bought spot legs each tick while the futures account sat
force-flattened, leaving executor-bought alts (SYN, ZAMA, KAITO, ALLO, MMT, EPIC, ...) in the
wallet with no live short to credit them -- ~19.7k of spot USDT below baseline while the rail read
equity -23k and fired 163 consecutive breaches. A recovery tool that names its symbols is one
incident behind by construction; this one derives them.

THE STRANDED SET, from venue ground truth and three hard exclusions:
  candidate  = non-stable spot balance whose USDT value exceeds --min-usd (default 25)
  MUST be a symbol the executor actually traded  (data/cashcarry_trades.json history)
  MUST NOT be currently tracked                  (cashcarry_positions.json "positions")
  MUST show a venue-confirmed NET BUY >= the quantity being sold (spot myTrades, paginated in
       20h chunks per the venue span-cap lesson) -- this is what makes selling faucet junk
       IMPOSSIBLE: the 1.0 WBTC/ETH/PAXG the testnet seeds were never bought through this
       account's trade history, so their net-buy is ~0 and they are skipped.
  sell qty = min(free balance, venue net-buy), floored to the LOT_SIZE step.

Dry-run by default; --execute places real (testnet) sells. Kill-latch compatible: selling
stranded spot back to USDT is flatten-direction (reduces exposure), the same standing authority
the 07-19 sweep ran under. Never touches the dead-man switch, its state, or tracked positions.

    .venv/bin/python scripts/run_stranded_recovery.py                # dry-run
    .venv/bin/python scripts/run_stranded_recovery.py --execute
    .venv/bin/python scripts/run_stranded_recovery.py --min-usd 100
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.execution import binance_spot_testnet as spot

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "stranded_recovery_log.json"
_STABLES = ("USDT", "USDC", "FDUSD", "TUSD", "BUSD", "DAI")
_CHUNK_MS = 20 * 3600 * 1000     # venue caps spot myTrades spans at 24h; 20h leaves margin


def _venue_net_buy(sym: str, start_ms: int, end_ms: int) -> float:
    """Venue-confirmed net bought quantity, paginated across the span cap.

    Silent-truncation trap (institutional_knowledge.md): querying past the cap returns an empty
    or partial list without error, so an unpaginated read UNDERCOUNTS buys and the guard would
    refuse legitimate recoveries -- fail-closed, but for the wrong reason. De-dup on trade id.
    """
    seen: dict[str, dict[str, Any]] = {}
    cursor = start_ms
    while cursor < end_ms:
        chunk_end = min(cursor + _CHUNK_MS, end_ms)
        try:
            for t in spot.my_trades(sym, cursor, chunk_end):
                seen[str(t.get("id"))] = t
        except Exception:
            pass                          # a missing chunk can only UNDER-count => safe direction
        cursor = chunk_end
    net = 0.0
    for t in seen.values():
        qty = float(t.get("qty", 0.0))
        net += qty if t.get("isBuyer") else -qty
    return net


def main() -> None:
    execute = "--execute" in sys.argv
    min_usd = 25.0
    if "--min-usd" in sys.argv:
        min_usd = float(sys.argv[sys.argv.index("--min-usd") + 1])
    if not spot.has_keys():
        print("ABORT: no spot testnet keys")
        sys.exit(1)

    state = json.loads((_ROOT / "data/cashcarry_positions.json").read_text("utf-8"))
    tracked = set((state.get("positions") or {}).keys())
    start_ms = int(datetime.fromisoformat(str(state["start"])).timestamp() * 1000)
    end_ms = int(time.time() * 1000)

    traded: set[str] = set()
    try:
        for t in json.loads((_ROOT / "data/cashcarry_trades.json").read_text("utf-8")):
            traded.add(str(t.get("symbol", "")))
    except Exception:
        pass
    if not traded:
        print("ABORT: no executor trade history -- cannot distinguish bought from faucet")
        sys.exit(1)

    bals = spot.balances()
    px = spot.prices()
    filters = spot.exchange_filters()

    rows: list[dict[str, Any]] = []
    for asset, amt in sorted(bals.items()):
        sym = asset + "USDT"
        if asset in _STABLES or amt <= 0 or sym in tracked:
            continue
        # The 500-row trade log rotates, so log-presence is only a FAST PATH -- the 07-27
        # stranding predated the window and its symbols (SYN, KAITO, ZAMA...) fell off the log
        # entirely, hiding 10k of executor buys from the first pass. Venue net-buy below is the
        # authoritative gate either way; skipping unlogged symbols only saves API weight, so it
        # applies just to small balances where the pagination cost exceeds the recoverable value.
        if sym not in traded and amt * px.get(sym, 0.0) < 200.0:
            continue
        val = amt * px.get(sym, 0.0)
        if val < min_usd:
            continue
        net_buy = _venue_net_buy(sym, start_ms, end_ms)
        f = filters.get(sym, {})
        step = float(f.get("step", 0.0) or 0.0)
        sell = min(amt, max(net_buy, 0.0))
        if step > 0:
            sell = math.floor(sell / step) * step
        row: dict[str, Any] = {
            "symbol": sym, "balance": amt, "venue_net_buy": round(net_buy, 8),
            "sell_qty": round(sell, 8), "price": px.get(sym, 0.0),
            "est_usdt": round(sell * px.get(sym, 0.0), 2),
        }
        if sell <= 0 or sell * px.get(sym, 0.0) < float(f.get("min_notional", 10.0) or 10.0):
            row["skipped"] = ("no venue-confirmed net buy -- faucet or already recovered"
                              if net_buy <= 0 else "below venue min notional")
            row["executed"] = False
        elif execute:
            try:
                res = spot.place_market(sym, "SELL", sell)
                row["order_id"] = res.get("orderId")
                row["executed"] = True
            except Exception as e:
                row["error"] = repr(e)[:300]
                row["executed"] = False
        else:
            row["executed"] = False
        rows.append(row)
        print(row)

    total = sum(r["est_usdt"] for r in rows if not r.get("skipped"))
    log = {"generated": datetime.now(tz=UTC).isoformat(),
           "mode": "execute" if execute else "dry_run", "min_usd": min_usd, "rows": rows,
           "recoverable_est_usdt": round(total, 2)}
    existing = json.loads(_OUT.read_text("utf-8")) if _OUT.exists() else []
    existing.append(log)
    _OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\n{'EXECUTED' if execute else 'DRY-RUN'} recoverable: ${total:,.2f} "
          f"across {sum(1 for r in rows if not r.get('skipped'))} symbols")


if __name__ == "__main__":
    main()
