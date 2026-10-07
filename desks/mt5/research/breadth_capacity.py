"""CAPACITY TERMS IN BREADTH CREDIT (open-ended alpha breadth law §15, BREADTH-0552..0557).

A new independent stream the desk cannot hold at size is less breadth than one it can. This module
prices six capacity terms for a candidate before any backtest, from what the tree already holds:

    capacity            the minimum-lot floor at this equity (reports/CAPACITY.json headroom):
                        a sleeve whose floor binds runs MORE risk than policy, so it is less
                        separately holdable. 1 / headroom when the floor binds, else 1
    turnover            trades/day implied by the chart, priced against the symbol's spread rank
    market_impact       UNMEASURED until the fill recorder locates an impact slope (CAPACITY.json
                        ceiling_status); an unmeasured term is 1.0, never a guess
    broker_constraints  the venue's registry: an unregistered symbol has no route (0.5); a
                        minimum volume above the volume step is a coarser lot ladder
    liquidity           sqrt(class-median spread / own spread), capped at 1 (a wide symbol for
                        its class is thinner)
    capital_efficiency  multi-day holds on a symbol with negative swap on BOTH sides pay
                        financing whichever way they lean

`factor` is the product, floored at CAPACITY_FLOOR so capacity re-orders breadth and never
erases it. PREREGISTERED 2026-10-06. ORDER AND BREADTH COUNTING ONLY: nothing here sizes a
position, caps capital, touches the allocator, a gate, a trial charge or a verdict -- capital is
the allocator's decision by dE[log W] (growth governance Rule 2), and this is not that.
"""
from __future__ import annotations

import json
import math
import statistics
from collections.abc import Mapping
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
UNIVERSE = DESK / "data" / "universe" / "universe.json"
CAPACITY = DESK / "reports" / "CAPACITY.json"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
TERMS = ("capacity", "turnover", "market_impact", "broker_constraints", "liquidity",
         "capital_efficiency")
CAPACITY_FLOOR = 0.25
#: Trades per day a chart implies (order of magnitude; preregistered).
TRADES_PER_DAY = {"M1": 8.0, "M5": 6.0, "M15": 4.0, "M30": 3.0, "H1": 2.0, "H4": 1.0,
                  "D1": 0.3, "W1": 0.1, "minute": 6.0, "intraday": 3.0, "hourly": 1.5,
                  "daily": 0.3}
#: Turnover drag per (trade/day x spread rank).
TURNOVER_K = 0.05
UNROUTED = 0.5
COARSE_LOT = 0.9
NEGATIVE_CARRY = 0.75
MULTI_DAY = ("swing", "position", "multi", "week", "month")


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


class Context:
    """The registry and the capacity report, read once per pass."""

    def __init__(self, universe: Mapping[str, Any] | None = None,
                 capacity: Mapping[str, Any] | None = None):
        u = universe if universe is not None else _read(UNIVERSE)
        self.universe: dict[str, Mapping[str, Any]] = {
            str(k).upper(): v for k, v in (u or {}).items() if isinstance(v, Mapping)}
        by_class: dict[str, list[float]] = {}
        for v in self.universe.values():
            sp = _num(v.get("median_spread_pts"))
            if sp and sp > 0:
                by_class.setdefault(str(v.get("asset_class")), []).append(sp)
        self.class_median = {k: statistics.median(v) for k, v in by_class.items() if v}
        c = capacity if capacity is not None else _read(CAPACITY)
        self.capacity_status = MEASURED if isinstance(c, Mapping) and c.get("rows") else UNMEASURED
        self.ceiling_status = str((c or {}).get("ceiling_status") or UNMEASURED) \
            if isinstance(c, Mapping) else UNMEASURED
        self.headroom: dict[str, float] = {}
        for r in ((c or {}).get("rows") or []) if isinstance(c, Mapping) else []:
            if isinstance(r, Mapping) and r.get("status") == MEASURED:
                h = _num(r.get("headroom_multiple"))
                sym = str(r.get("symbol") or "").upper()
                if h is not None and sym:
                    self.headroom[sym] = max(self.headroom.get(sym, 0.0), h)


def terms(symbol: str, axes: Mapping[str, Any], ctx: Context) -> dict[str, Any]:
    """The six terms for one candidate: {term: factor or None}, statuses and the product."""
    sym = str(symbol or "").upper()
    reg = ctx.universe.get(sym)
    f: dict[str, float | None] = {}
    why: dict[str, str] = {}
    h = ctx.headroom.get(sym)
    if h is not None:
        f["capacity"] = 1.0 / h if h > 1.0 else 1.0
    else:
        f["capacity"] = None
        why["capacity"] = ("CAPACITY.json absent" if ctx.capacity_status == UNMEASURED
                           else "no measured sleeve on this symbol")
    sp = _num((reg or {}).get("median_spread_pts"))
    med = ctx.class_median.get(str((reg or {}).get("asset_class")))
    rank = (sp / med) if sp and sp > 0 and med else None
    tpd = TRADES_PER_DAY.get(str(axes.get("timeframe") or ""))
    if rank is not None and tpd is not None:
        f["turnover"] = 1.0 / (1.0 + TURNOVER_K * tpd * rank)
    else:
        f["turnover"] = None
        why["turnover"] = "no measured spread or no chart"
    f["market_impact"] = None
    why["market_impact"] = f"impact ceiling {ctx.ceiling_status} (fill recorder)"
    if not ctx.universe:
        f["broker_constraints"] = None
        why["broker_constraints"] = "universe registry absent"
    elif reg is None:
        f["broker_constraints"] = UNROUTED
    else:
        mv, st = _num(reg.get("min_volume") or reg.get("volume_min")), _num(reg.get("volume_step"))
        f["broker_constraints"] = COARSE_LOT if (mv and st and mv > st) else 1.0
    if rank is not None:
        f["liquidity"] = min(1.0, math.sqrt(1.0 / rank))
    else:
        f["liquidity"] = None
        why["liquidity"] = "no measured spread for this symbol or its class"
    sl, ss = _num((reg or {}).get("swap_long")), _num((reg or {}).get("swap_short"))
    hor = str(axes.get("horizon") or "").lower()
    if sl is None or ss is None:
        f["capital_efficiency"] = None
        why["capital_efficiency"] = "no swap rates in the registry"
    else:
        multi = any(t in hor for t in MULTI_DAY)
        f["capital_efficiency"] = NEGATIVE_CARRY if (multi and sl < 0 and ss < 0) else 1.0
    prod = 1.0
    for v in f.values():
        if v is not None:
            prod *= v
    return {"factor": round(max(CAPACITY_FLOOR, prod), 6),
            "terms": {k: (round(v, 6) if v is not None else None) for k, v in f.items()},
            "unmeasured": why}


__all__ = ["CAPACITY_FLOOR", "TERMS", "Context", "terms"]
