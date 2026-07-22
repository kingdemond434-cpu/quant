"""Execution cost model from the recorded L2 moat -- the Gate-0 `cost_model` criterion.

Walks the ACTUAL recorded order books (data/moat/{spot,fut}/SYM/*.jsonl.gz, top-20 both sides)
to answer the only question that matters for a delta-neutral carry desk:

    "If I open a $N carry in symbol X, what does the spot BUY + perp SELL pair actually cost me
     in slippage, and does the book even hold that size?"

This is measured, not assumed -- it replaces the `adv_tier_cost` heuristic and calibrates the
executor's `_DEPTH_MULT` guard with real numbers. Read-only: touches nothing but data/moat and
writes data/cost_model.json. Freeze-safe.

Slippage convention: signed bps of the mid at snapshot time, positive = adverse.
    BUY  : (vwap_paid     / mid - 1) * 1e4
    SELL : (1 - vwap_recv / mid)     * 1e4
Pair cost = spot BUY + perp SELL (one open). Round-trip doubles it (open + close).
"""
from __future__ import annotations

import gzip
import json
import statistics
from pathlib import Path
from typing import Any

_MOAT = Path("data/moat")
_OUT = Path("data/cost_model.json")
_SIZES = [100.0, 250.0, 500.0, 1000.0, 2500.0]   # USDT notional per leg
_MAX_SNAPSHOTS = 300                              # per symbol per leg (sampled across all hours)


def _walk(levels: list[list[str]], notional: float) -> tuple[float, bool]:
    """VWAP to fill `notional` USDT against these price levels. Returns (vwap, exhausted)."""
    spent = 0.0
    qty_acc = 0.0
    for px_s, qty_s in levels:
        px, qty = float(px_s), float(qty_s)
        if px <= 0 or qty <= 0:
            continue
        avail = px * qty
        take = min(avail, notional - spent)
        if take <= 0:
            break
        qty_acc += take / px
        spent += take
        if spent >= notional - 1e-9:
            break
    if qty_acc <= 0:
        return 0.0, True
    return spent / qty_acc, spent < notional - 1e-6      # exhausted = book too thin


def _snapshots(sym_dir: Path, limit: int) -> list[dict[str, Any]]:
    """Evenly sample depth records across ALL recorded hours (not just the newest)."""
    files = sorted(sym_dir.glob("*.jsonl.gz"))
    if not files:
        return []
    per_file = max(1, limit // len(files))
    out: list[dict[str, Any]] = []
    for fp in files:
        taken = 0
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if taken >= per_file:
                        break
                    if i % 7:                    # thin out within the hour
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if r.get("k") == "d" and r.get("b") and r.get("a"):
                        out.append(r)
                        taken += 1
        except (OSError, EOFError):
            continue
    return out


def _leg_costs(sym_dir: Path, side: str) -> dict[str, Any]:
    """side='buy' walks asks (spot open); side='sell' walks bids (perp open)."""
    snaps = _snapshots(sym_dir, _MAX_SNAPSHOTS)
    if not snaps:
        return {}
    per_size: dict[str, Any] = {}
    for size in _SIZES:
        bps_list: list[float] = []
        exhausted = 0
        for r in snaps:
            bids, asks = r["b"], r["a"]
            try:
                best_bid, best_ask = float(bids[0][0]), float(asks[0][0])
            except (IndexError, ValueError):
                continue
            mid = (best_bid + best_ask) / 2.0
            if mid <= 0:
                continue
            levels = asks if side == "buy" else bids
            vwap, ex = _walk(levels, size)
            if ex or vwap <= 0:
                exhausted += 1
                continue
            bps = ((vwap / mid - 1.0) if side == "buy" else (1.0 - vwap / mid)) * 1e4
            bps_list.append(bps)
        n = len(bps_list)
        per_size[str(int(size))] = {
            "n": n,
            "exhausted_frac": round(exhausted / max(1, len(snaps)), 4),
            "median_bps": round(statistics.median(bps_list), 3) if n else None,
            "p90_bps": round(sorted(bps_list)[int(n * 0.9)], 3) if n >= 10 else None,
        }
    return per_size


def main() -> None:
    fut_root, spot_root = _MOAT / "fut", _MOAT / "spot"
    symbols = sorted({p.name for p in fut_root.iterdir() if p.is_dir()} &
                     {p.name for p in spot_root.iterdir() if p.is_dir()}) if (
        fut_root.exists() and spot_root.exists()) else []
    model: dict[str, Any] = {"symbols": {}, "sizes_usdt": _SIZES,
                             "convention": "signed bps of mid, positive = adverse; "
                                           "pair = spot BUY + perp SELL (one open)"}
    for sym in symbols:
        spot_c = _leg_costs(spot_root / sym, "buy")
        fut_c = _leg_costs(fut_root / sym, "sell")
        if not spot_c or not fut_c:
            continue
        pair: dict[str, Any] = {}
        for k in spot_c:
            sb, fs = spot_c[k].get("median_bps"), fut_c[k].get("median_bps")
            pair[k] = {
                "pair_open_bps": round(sb + fs, 3) if (sb is not None and fs is not None) else None,
                "pair_roundtrip_bps": round(2 * (sb + fs), 3) if (
                    sb is not None and fs is not None) else None,
                "worst_exhausted_frac": max(spot_c[k]["exhausted_frac"],
                                            fut_c[k]["exhausted_frac"]),
            }
        model["symbols"][sym] = {"spot_buy": spot_c, "fut_sell": fut_c, "pair": pair}
        print(f"{sym:12s} pair@500={pair.get('500', {}).get('pair_open_bps')} bps  "
              f"pair@2500={pair.get('2500', {}).get('pair_open_bps')} bps")

    # desk-level summary at the size the book actually trades (~$450/carry -> use 500)
    at500 = [(s, d["pair"]["500"]["pair_open_bps"]) for s, d in model["symbols"].items()
             if d["pair"].get("500", {}).get("pair_open_bps") is not None]
    at500.sort(key=lambda kv: kv[1])
    model["summary"] = {
        "n_symbols": len(model["symbols"]),
        "cheapest_at_500": at500[:5],
        "most_expensive_at_500": at500[-5:],
        "median_pair_open_bps_at_500": round(statistics.median([v for _, v in at500]), 3)
        if at500 else None,
    }
    _OUT.write_text(json.dumps(model, indent=1), "utf-8")
    print("\nwrote", _OUT, "| symbols:", len(model["symbols"]))
    med = model["summary"]["median_pair_open_bps_at_500"]
    print("median pair-open cost @ $500/leg:", med, "bps")


if __name__ == "__main__":
    main()
