"""Recover spot inventory stranded by the confirmed root cause of the 2026-07-19 dead-man fire.

Root cause (verified against code + venue records, GAP register row 34): `_execute_pair`'s
market-order fallback in scripts/run_cashcarry_executor.py wraps every order in `with _safe():`,
which swallows ALL exceptions with zero fill verification. The CLOSE path then unconditionally
logs success and deletes the position from tracking regardless of whether the sell actually
filled. For GTCUSDT/SHELLUSDT/ONEUSDT the close orders never filled on-venue: the position was
deleted from `pos` (so no reconciler ever revisits it) while 100% of the real spot inventory
stayed in the wallet, invisible to both the tracker and the dead-man's `legs_v` (which only counts
symbols with a currently-live futures short -- these no longer have one).

This script does NOT touch scripts/run_deadman_switch.py, its state files, or the executor's
tracked positions (these symbols are already absent from data/cashcarry_positions.json). It only
sells now-untracked, already-owned spot dust back to USDT -- a recovery action within existing
standing trading authority, not a new position or a fund transfer.

    .venv/bin/python scripts/run_deadman_stranded_sweep.py           # dry-run (default)
    .venv/bin/python scripts/run_deadman_stranded_sweep.py --execute # place real (testnet) orders
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import libs.execution.binance_spot_testnet as spot

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data" / "deadman_stranded_sweep_log.json"
_SYMBOLS = ("GTCUSDT", "SHELLUSDT", "ONEUSDT")  # confirmed stranded (row 34 forensic scan);
# COOKIE/MOVE/HFT/C98/IOTX/CRV/BICO/JASMY/TST/XVG checked and confirmed zero -- their closes
# executed cleanly. Add a symbol here only after confirming a non-zero, currently-untracked
# balance via spot.balances() -- never sweep a symbol still present in cashcarry_positions.json.


def main() -> None:
    execute = "--execute" in sys.argv
    if not spot.has_keys():
        print("ABORT: no spot testnet keys")
        sys.exit(1)

    tracked = set(json.loads((_ROOT / "data" / "cashcarry_positions.json").read_text("utf-8"))
                  .get("positions", {}))
    bals = spot.balances()
    px = spot.prices()
    filters = spot.exchange_filters()

    rows: list[dict[str, Any]] = []
    for sym in _SYMBOLS:
        base = sym.replace("USDT", "")
        if sym in tracked:
            print(f"SKIP {sym}: still a tracked live position -- never sweep a live carry leg")
            continue
        qty = bals.get(base, 0.0)
        price = px.get(sym, 0.0)
        if qty <= 0 or price <= 0:
            print(f"SKIP {sym}: no balance ({qty})")
            continue
        fl = filters.get(sym, {})
        step = fl.get("step", 0.0) or 0.0
        prec = int(fl.get("qty_prec", 6))
        sell_qty = round(qty - (qty % step), prec) if step else round(qty, prec)
        est_usdt = round(sell_qty * price, 2)
        row = {"symbol": sym, "qty_held": qty, "sell_qty": sell_qty,
               "price": price, "est_usdt": est_usdt}
        if execute and sell_qty > 0:
            try:
                res = spot.place_market(sym, "SELL", sell_qty)
                row["order_result"] = res
                row["executed"] = True
            except Exception as e:
                row["error"] = repr(e)[:300]
                row["executed"] = False
        else:
            row["executed"] = False
        rows.append(row)
        print(row)

    log = {"generated": datetime.now(UTC).isoformat(), "mode": "execute" if execute else "dry_run",
           "rows": rows, "total_est_usdt": round(sum(r["est_usdt"] for r in rows), 2)}
    existing = json.loads(_OUT.read_text("utf-8")) if _OUT.exists() else []
    existing.append(log)
    _OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\n{'EXECUTED' if execute else 'DRY-RUN'} total: ${log['total_est_usdt']}")
    print(f"Logged to {_OUT}")


if __name__ == "__main__":
    main()
