"""CAPACITY SIMULATOR -- what is the MINIMUM viable live capital, from the venue's real filters?

Replaces a rule-of-thumb with the exchange's actual constraints. The principal asked "how much at
Gate-0"; the honest answer is computable, not estimable.

THREE BINDING CONSTRAINTS, per symbol, per leg:
  1. MIN_NOTIONAL  -- the venue rejects orders below it outright.
  2. LOT_SIZE step -- quantity is rounded DOWN to a step. At small notional the discarded remainder
     is a large % of the order, so the book silently under-deploys and the two legs stop matching
     (a delta-neutral carry with mismatched legs is no longer delta-neutral -- this is the real
     risk, not the fee).
  3. Slippage      -- from the desk's MEASURED cost model (recorded L2), which shows slippage
     RISING with size (AAVE spot: 0.51bps @ $100 -> 1.97bps @ $2500). So small size is BETTER for
     impact; the floor is set by rounding, not by market impact.

Outputs the minimum per-leg notional that keeps rounding error under a target (default 1%), then
the per-carry and whole-book minimum for the LIVE universe.

Read-only, no keys, public endpoints. Run from repo root.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "web/cashcarry_live.json"
COST = ROOT / "data/cost_model.json"
OUT = ROOT / "data/capacity_floor.json"

MAX_ROUNDING_ERR = 0.01  # 1% of an order lost to lot-step rounding is the tolerance
SAFETY = 1.5  # buffer so a price move does not push an order under the minimum


def _get(u, t=30):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "q/1.0"}), timeout=t
        )
        .read()
        .decode()
    )


def filters(info: dict) -> dict[str, dict]:
    out = {}
    for s in info.get("symbols", []):
        f = {x["filterType"]: x for x in s.get("filters", [])}
        step = float(f.get("LOT_SIZE", {}).get("stepSize", 0) or 0)
        # G2 FIX: spot uses key "minNotional"; USD-M FUTURES uses "notional". Reading only
        # "minNotional" returned 0.0 for every futures symbol -> the floor was UNDERSTATED.
        mnf = f.get("MIN_NOTIONAL", {}) or f.get("NOTIONAL", {})
        mn = float(mnf.get("minNotional") or mnf.get("notional") or 0)
        out[s["symbol"]] = {"step": step, "min_notional": mn}
    return out


def main() -> None:
    syms = []
    if LIVE.exists():
        d = json.loads(LIVE.read_text("utf-8"))
        syms = [c["symbol"] for c in d.get("carries", []) if c.get("symbol")]
    if not syms:
        syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    print(f"=== CAPACITY FLOOR | live carry universe: {len(syms)} symbols ===")
    print(
        f"    tolerance: <={MAX_ROUNDING_ERR * 100:.0f}% of an order lost to lot rounding, "
        f"x{SAFETY} safety buffer\n"
    )

    spot_f = filters(_get("https://api.binance.com/api/v3/exchangeInfo"))
    fut_f = filters(_get("https://fapi.binance.com/fapi/v1/exchangeInfo"))
    px = {
        r["symbol"]: float(r["price"])
        for r in _get("https://api.binance.com/api/v3/ticker/price")
        if r["symbol"] in syms
    }

    rows, floors = [], []
    print(
        f"  {'symbol':<12}{'price':>11}{'spot min':>10}{'fut min':>9}"
        f"{'round-floor':>12}{'PER-LEG':>9}"
    )
    for s in syms:
        p = px.get(s)
        sf, ff = spot_f.get(s), fut_f.get(s)
        if not p or not sf or not ff:
            print(f"  {s:<12} (missing filter/price data)")
            continue
        # notional at which one lot-step is <= MAX_ROUNDING_ERR of the order
        step_val = max(sf["step"], ff["step"]) * p
        round_floor = step_val / MAX_ROUNDING_ERR if step_val > 0 else 0.0
        venue_min = max(sf["min_notional"], ff["min_notional"])
        leg = max(round_floor, venue_min) * SAFETY
        floors.append(leg)
        rows.append(
            {
                "symbol": s,
                "price": p,
                "spot_min": sf["min_notional"],
                "fut_min": ff["min_notional"],
                "round_floor": round(round_floor, 2),
                "per_leg_min": round(leg, 2),
            }
        )
        print(
            f"  {s:<12}{p:>11.5f}{sf['min_notional']:>10.1f}{ff['min_notional']:>9.1f}"
            f"{round_floor:>12.2f}{leg:>9.2f}"
        )

    if not floors:
        print("\nno usable symbols")
        return
    worst = max(floors)
    median = sorted(floors)[len(floors) // 2]
    n = len(floors)
    # a carry funds BOTH legs: spot bought outright + futures margin at 1x
    per_carry_worst, per_carry_med = worst * 2, median * 2

    print(f"\n  binding symbol needs ${worst:,.2f}/leg  |  median ${median:,.2f}/leg")
    print(
        f"  per-carry (spot + perp legs): worst ${per_carry_worst:,.2f} | "
        f"median ${per_carry_med:,.2f}"
    )
    print("\n  === MINIMUM VIABLE BOOK ===")
    for k in (3, 5, 10, n):
        if k <= 0:
            continue
        print(
            f"    {k:>2} carries : ${per_carry_med * k:>10,.0f}  (median-symbol universe)"
            f"   ${per_carry_worst * k:>10,.0f}  (if the binding symbol is included)"
        )
    print("\n  NOTE: slippage does NOT bind here -- the measured cost model shows impact RISING")
    print("  with size, so small orders are cheaper. The floor is LOT ROUNDING, and the real risk")
    print("  of breaching it is LEG MISMATCH: if spot and perp round differently the position")
    print("  stops being delta-neutral, which is a directional bet the strategy never intended.")

    if COST.exists():
        cm = json.loads(COST.read_text("utf-8"))
        print("")
        print("  === SLIPPAGE SANITY (a degenerate entry is worse than none) ===")
        for sym0 in syms:
            b = cm.get("symbols", {}).get(sym0, {}).get("spot_buy", {})
            if not b:
                continue
            pts = sorted((int(k), v.get("median_bps", 0.0)) for k, v in b.items())
            vals = [v for _, v in pts]
            flat = len({round(v, 3) for v in vals}) == 1 and len(vals) > 2
            worst = max(vals) if vals else 0.0
            rt = worst * 4 / 100.0  # 4 legs: open spot, open perp, close spot, close perp
            tag = ""
            if flat:
                tag = "  <-- DEGENERATE: flat across all buckets, not physically plausible"
            elif rt > 0.7:
                tag = f"  <-- UNPROFITABLE: {rt:.2f}% round-trip vs ~0.7%/mo harvest"
            print(f"    {sym0:<14}" + " ".join(f"${k}:{v:.1f}" for k, v in pts[:5]) + tag)

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "tolerance_rounding": MAX_ROUNDING_ERR,
                "safety": SAFETY,
                "per_leg_worst": round(worst, 2),
                "per_leg_median": round(median, 2),
                "per_carry_median": round(per_carry_med, 2),
                "book_10_carries_median": round(per_carry_med * 10, 2),
                "symbols": rows,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
