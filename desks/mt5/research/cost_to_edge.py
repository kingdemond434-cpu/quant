"""What a sleeve PAYS to trade, against what it earns. The cost the backtest never charged.

THE ENGINE DOES NOT MODEL SWAP. `mt5desk.engine.Costs` carries spread_per_lot,
commission_per_lot, contract_oz and quote_per_account -- and nothing else. Grep the module for
"swap" and it is empty. So every certificate this desk has ever minted was judged with ZERO
overnight financing cost.

For an intraday sleeve that is correct and costs nothing. For `overnight_gap_decay` it is the
whole ballgame: that family holds through rollover BY CONSTRUCTION, so the one cost that dominates
it was never charged.

MEASURED 2026-09-14 on the four live overnight_gap_decay sleeves, cost per round trip with one
night held, as a fraction of a 2xATR20 stop:

    symbol    spread_R   swap_R   total_R
    CHFDKK      0.052     0.053     0.105
    EURNOK      0.100     0.027     0.127
    GBPNOK      0.191     0.011     0.202
    GBPMXN      0.186     0.061     0.246

Against a net expectancy assumption of +0.135R, GBPMXN and GBPNOK cost MORE THAN THE ENTIRE EDGE
they exist to capture. EURNOK eats three quarters of it. For scale, EURUSD measures ~0.025R.
And all four carry the same parameter hash -- one hypothesis replicated onto four instruments
whose cost structure destroys it, at the thinnest liquidity hour of the day.

WHY A FENCE RATHER THAN A MODEL CHANGE. Adding swap to `Costs` is the right end state and it
re-prices every certificate the desk holds -- a large, careful change that should not be made at
speed on a live book. This measures the same thing from the broker's own numbers and refuses the
sleeves where cost exceeds edge, which protects capital today. The model change can follow.

COMMISSION IS ALREADY CONSERVATIVE and is not the problem. Real fills charge EUR 2.00/lot per
side (EUR 4.00 round turn); `Costs` charges 3.50 twice, EUR 7.00. It over-charges by 75%, in the
safe direction, which is why spread and swap are what this measures.

    python desks/mt5/research/cost_to_edge.py
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
SLEEVES = BASE / "data" / "sleeves.json"
OUT = BASE / "reports" / "COST_TO_EDGE.json"

#: Most of a sleeve's measured edge that round-trip cost may consume before it is refused.
#:
#: HALF IS NOT ARBITRARY. Cost is measured with far more confidence than edge: a spread is a
#: quote and a swap is a published rate, while exp_r is an estimate from a few dozen trades with
#: a standard error of its own. A sleeve whose central estimate leaves half its edge after costs
#: is one bad estimate away from zero, and the estimate is the half that is uncertain.
MAX_COST_FRACTION_OF_EDGE = 0.50

#: Nights a position is assumed to be held when its family holds through rollover. One is the
#: floor, not the mean: `overnight_gap_decay` enters before a session close and exits after the
#: gap, so one night is the MINIMUM it pays and the honest lower bound on the charge.
NIGHTS_HELD = 1.0

#: Families that hold through rollover by construction. Anything not here is charged spread and
#: commission only, because an intraday sleeve genuinely pays no financing.
OVERNIGHT_FAMILIES = ("overnight_gap_decay", "carry", "turn_of_month", "dow_effect")


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def symbol_cost_r(sym: str, family: str = "", mt5: Any = None) -> dict[str, Any]:
    """Round-trip cost for one symbol as a fraction of a 2xATR20 stop. UNMEASURED when it cannot.

    Absence is a verdict here and never a zero: a symbol whose cost cannot be read must not pass
    a cost fence by default, which is exactly how an unpriced instrument gets funded.
    """
    out: dict[str, Any] = {"symbol": sym, "family": family, "measured": False}
    if mt5 is None:
        try:
            import MetaTrader5 as _mt5
            mt5 = _mt5
        except ImportError:
            out["why"] = "MetaTrader5 unavailable on this host"
            return out
    if mt5.terminal_info() is None and not mt5.initialize():
        out["why"] = "terminal not initialised"
        return out
    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if info is None or tick is None:
        out["why"] = f"{sym} is not quoted on this account"
        return out
    try:
        import pandas as pd
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 500)
        df = pd.DataFrame(rates)
        atr = float((df["high"] - df["low"]).rolling(20).mean().iloc[-1])
    except Exception as exc:
        out["why"] = f"cannot measure ATR: {type(exc).__name__}"
        return out
    point = float(info.point) or 1e-9
    stop_pts = 2.0 * atr / point
    if not (stop_pts > 0):
        out["why"] = "ATR is zero: no usable stop distance"
        return out
    spread_pts = (float(tick.ask) - float(tick.bid)) / point
    # THE WORSE SIDE, ALWAYS. A sleeve may be long or short and the desk does not get to choose
    # the cheaper financing after the fact; charging the favourable side would price a trade the
    # book cannot guarantee it is taking.
    swap_pts = max(abs(float(info.swap_long)), abs(float(info.swap_short)))
    holds = any(f in str(family) for f in OVERNIGHT_FAMILIES)
    swap_charge = swap_pts * NIGHTS_HELD if holds else 0.0
    out.update({
        "measured": True,
        "stop_pts": round(stop_pts, 1),
        "spread_pts": round(spread_pts, 1),
        "swap_pts_worse_side": round(swap_pts, 2),
        "holds_overnight": holds,
        "spread_r": round(spread_pts / stop_pts, 4),
        "swap_r": round(swap_charge / stop_pts, 4),
        "total_cost_r": round((spread_pts + swap_charge) / stop_pts, 4),
    })
    return out


def verdict(sym: str, family: str, edge_r: float | None,
            mt5: Any = None) -> tuple[bool, str, dict[str, Any]]:
    """(refuse, why, detail). Refuses when measured cost eats too much of measured edge."""
    c = symbol_cost_r(sym, family, mt5=mt5)
    if not c.get("measured"):
        return False, "", c          # unmeasured cost is reported, never a silent refusal
    if edge_r is None or not (float(edge_r) > 0):
        return False, "", c          # no edge measured yet: the clock decides, not this
    frac = float(c["total_cost_r"]) / float(edge_r)
    c["cost_fraction_of_edge"] = round(frac, 3)
    if frac <= MAX_COST_FRACTION_OF_EDGE:
        return False, "", c
    return True, (f"round-trip cost {c['total_cost_r']:.3f}R "
                  f"(spread {c['spread_r']:.3f} + swap {c['swap_r']:.3f}) is "
                  f"{frac:.0%} of the measured edge {float(edge_r):.3f}R, over the "
                  f"{MAX_COST_FRACTION_OF_EDGE:.0%} bar. The engine charges NO swap, so this "
                  f"cost was never in the backtest that certified it"), c


def main() -> int:
    doc = _read(SLEEVES, [])
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    live = [r for r in (rows or [])
            if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"]
    results: list[dict[str, Any]] = []
    for r in live:
        name = str(r.get("name") or "")
        sym = name.split("_")[0].upper()
        fam = str(r.get("family") or "")
        if not fam:
            for f in OVERNIGHT_FAMILIES:
                if f in name:
                    fam = f
                    break
        c = symbol_cost_r(sym, fam)
        c["sleeve"] = name
        results.append(c)

    measured = [c for c in results if c.get("measured")]
    measured.sort(key=lambda c: -float(c.get("total_cost_r") or 0))
    out = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": ("the backtest engine models NO swap: mt5desk.engine.Costs has spread and "
                 "commission only, so every overnight-holding certificate was judged with zero "
                 "financing cost"),
        "max_cost_fraction_of_edge": MAX_COST_FRACTION_OF_EDGE,
        "n_live": len(live),
        "n_measured": len(measured),
        "by_cost": measured[:40],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"cost-to-edge: {len(measured)} of {len(live)} live sleeve(s) priced")
    print(f"{'sleeve':44} {'spread_R':>9} {'swap_R':>8} {'total_R':>8}")
    for c in measured[:15]:
        print(f"{str(c['sleeve'])[:44]:44} {c['spread_r']:9.3f} {c['swap_r']:8.3f} "
              f"{c['total_cost_r']:8.3f}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
