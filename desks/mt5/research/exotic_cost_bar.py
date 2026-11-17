"""THE STRICT EXOTIC COST BAR: an exotic earns live capital only if it still pays at 2x its costs.

The principal, 2026-11-13 19:45Z: "Every time we tried any exotic btw it turned out to be a false
edge", then 19:46Z: "Yes do the strict cost bar". The standing rule: a clock on an exotic FX
symbol (MetaTrader's own registry class, `asset_class` "Forex Exotics" in universe.json, never a
symbol list) is eligible for promotion and for the live account ONLY while its forward
expectancy survives TWICE the measured spread at the hour it actually fills, plus twice the
worse-side overnight swap when the family holds through rollover.

WHY THIS BAR AND NOT A HAIRCUT (the forensic of the same day, measured on origin's
reports/shadow/shadow_state.json and data/cost_surface.json). The forward clocks charge ONE pooled
median spread per symbol (`shadow_forward.per_symbol_costs` -> `Costs.from_symbol`, no hour), and
the exotic candidates fill at broker hour 00-01, the rollover dead book:

    GBPSEK pooled 246 pts, hour-01 median 698, hour-00 median 2,952
    CHFNOK pooled 267 pts, hour-00 median 4,511 (2.3x its own H1 ATR)
    GBPMXN pooled 327 pts, hour-00 median 4,633

So a forward clock read +0.6R on a book whose real entry cost was a full R or more. The live
ledger agrees: of the six exotics that reached the account, five closed net negative (USDNOK -21
over 23 trades, CHFNOK -10 over 17, EURZAR, GBPSEK, GBPMXN) and one is flat (USDMXN, 1 trade).
The research gauntlet already charges the fill hour
(`external_gauntlet.build_cell`) and stresses that spread at 3x, so a fresh STILL_PASSES re-grade
covers the backtest side; THIS covers the forward clock, which never did.

THE ARITHMETIC, in R = 2 x ATR20(H1) points (the desk's cost-in-R convention,
`research/cost_to_edge.symbol_cost_r`), all inputs on disk, no terminal needed:

    gross   = exp_r + charged_spread / R           (what the clock charged, added back: the
                                                     pooled median, or its frozen fill-hour spread;
                                                     swap assumed NOT charged -- conservative)
    net_2x  = gross - 2 x (fill_hour_spread + swap_worse_side) / R
    PASS iff net_2x > 0

fill_hour_spread is the WORST measured median across the hours the clock has filled in
(first and last entry). Any input missing is UNMEASURED, and UNMEASURED fails closed: an exotic
whose cost cannot be priced is not an edge anyone has measured (principal 2026-09-29, "UNKNOWN
COST IS UNKNOWN EDGE").

A library, not a process: the hourly leg `policy_lift_reopen` builds and writes
reports/EXOTIC_COST_BAR.json on every pass, immediately before the promoter. It is read by
`mt5desk.live_policy.refuse` (promoter, gateway and the reopen leg all go through it)
whenever data/live_sleeve_policy.json carries `exotic_cost_bar`.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe" / "universe.json"
SURFACE = BASE / "data" / "cost_surface.json"
SHADOW_DIR = BASE / "reports" / "shadow"
REPORT = BASE / "reports" / "EXOTIC_COST_BAR.json"
LANE_FILES = ("shadow_state.json", "qquant_shadow_state.json", "scalp_shadow_state.json")

#: The principal's multiplier (2026-11-13 19:46Z).
COST_MULTIPLIER = 2.0
#: Families that hold through rollover by construction (`cost_to_edge.OVERNIGHT_FAMILIES`).
OVERNIGHT_FAMILIES = ("overnight_gap_decay", "carry", "turn_of_month", "dow_effect")
RULE = ("principal 2026-11-13 19:46Z 'do the strict cost bar': an exotic FX clock is eligible "
        "for promotion and live capital only while forward expectancy survives 2x the measured "
        "fill-hour spread and 2x the worse-side swap; unmeasured fails closed")


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def exotic_symbols(universe: dict[str, Any]) -> frozenset[str]:
    """Every symbol MetaTrader's registry classes as an exotic. Never a hand list."""
    return frozenset(str(s).upper() for s, m in universe.items()
                     if isinstance(m, dict)
                     and "exotic" in str(m.get("asset_class") or "").lower())


def _symbol_family(key: str, st: dict[str, Any]) -> tuple[str, str]:
    sym = str(st.get("symbol") or key.split(".", 1)[0]).upper()
    parts = key.split(".")
    fam = str(st.get("family") or (parts[1] if len(parts) > 1 else ""))
    return sym, fam


def _fill_hours(st: dict[str, Any]) -> list[int]:
    hours = set()
    for f in ("first_entry", "last_entry"):
        v = str(st.get(f) or "")
        if len(v) >= 13 and v[11:13].isdigit():
            hours.add(int(v[11:13]))
    return sorted(hours)


def _hour_spread(surface: dict[str, Any], sym: str, hour: int) -> float | None:
    cell = (((surface.get("symbols") or {}).get(sym) or {}).get("hours") or {}).get(str(hour))
    if (not isinstance(cell, dict) or cell.get("status") != "MEASURED"
            or cell.get("p50") is None):
        return None
    return float(cell["p50"])


def _swap_worse_pts(meta: dict[str, Any]) -> float | None:
    try:
        from mt5desk.engine import swap_night_points
    except ImportError:                                    # pragma: no cover - desk path only
        return None
    worst: float | None = None
    for side in ("swap_long", "swap_short"):
        if meta.get(side) is None:
            return None
        pts, _why = swap_night_points(meta, float(meta[side]), None)
        if pts is None:
            return None
        worst = abs(pts) if worst is None else max(worst, abs(pts))
    return worst


def judge(key: str, st: dict[str, Any], universe: dict[str, Any], surface: dict[str, Any],
          mult: float = COST_MULTIPLIER) -> dict[str, Any]:
    """PASS / FAIL / UNMEASURED for one exotic clock, with every number that decided it."""
    sym, fam = _symbol_family(key, st)
    out: dict[str, Any] = {"symbol": sym, "family": fam, "multiplier": mult}
    meta = universe.get(sym) or {}
    try:
        exp = float(st["exp_r"])
    except (KeyError, TypeError, ValueError):
        return {**out, "verdict": "UNMEASURED", "why": "no forward expectancy on the clock"}
    hours = _fill_hours(st)
    if not hours:
        return {**out, "verdict": "UNMEASURED", "why": "the clock has no fill hour yet"}
    spreads = [_hour_spread(surface, sym, h) for h in hours]
    if any(s is None for s in spreads):
        return {**out, "verdict": "UNMEASURED", "fill_hours": hours,
                "why": "fill-hour spread not measured on the cost surface"}
    atr = ((surface.get("symbols") or {}).get(sym) or {}).get("atr20_h1_pts")
    pooled_raw = meta.get("median_spread_pts")
    if not atr or float(atr) <= 0 or pooled_raw is None:
        return {**out, "verdict": "UNMEASURED", "why": "ATR20 or pooled spread missing"}
    r_pts = 2.0 * float(atr)
    pooled = float(pooled_raw)
    hs = max(float(s) for s in spreads if s is not None)
    swap = 0.0
    if any(f in fam for f in OVERNIGHT_FAMILIES):
        sw = _swap_worse_pts(meta)
        if sw is None:
            return {**out, "verdict": "UNMEASURED", "why": "overnight family with unpriced swap"}
        swap = sw
    # WHAT THE CLOCK ACTUALLY CHARGED is added back: the pooled median, or -- once the clock
    # runs on its fill-hour basis (shadow_forward.fill_hour_costs) -- the frozen hour spread.
    charged = st.get("spread_pts_charged")
    try:
        charged_pts = float(charged) if charged is not None else pooled
    except (TypeError, ValueError):
        charged_pts = pooled
    gross = exp + charged_pts / r_pts
    net_1x = gross - (hs + swap) / r_pts
    net_mx = gross - mult * (hs + swap) / r_pts
    return {**out, "verdict": "PASS" if net_mx > 0 else "FAIL",
            "exp_r_clock": round(exp, 4), "fill_hours": hours,
            "fill_hour_spread_pts": hs, "pooled_spread_pts": pooled,
            "spread_pts_charged_by_clock": charged_pts,
            "swap_worse_pts": round(swap, 2), "r_pts": round(r_pts, 1),
            "net_r_at_1x": round(net_1x, 4), "net_r_at_bar": round(net_mx, 4)}


def build(lanes: list[dict[str, Any]], universe: dict[str, Any],
          surface: dict[str, Any]) -> dict[str, Any]:
    exo = exotic_symbols(universe)
    rows: dict[str, dict[str, Any]] = {}
    for lane in lanes:
        states = lane.get("sleeves") if isinstance(lane.get("sleeves"), dict) else lane
        for k, st in (states or {}).items():
            if not isinstance(st, dict):
                continue
            sym, _fam = _symbol_family(str(k), st)
            if sym in exo:
                rows[str(k)] = judge(str(k), st, universe, surface)
    count = {v: sum(1 for r in rows.values() if r["verdict"] == v)
             for v in ("PASS", "FAIL", "UNMEASURED")}
    return {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"), "rule": RULE,
            "multiplier": COST_MULTIPLIER,
            "r_basis": "2 x ATR20(H1) points (cost_to_edge convention)",
            "n_exotic_clocks": len(rows), "counts": count,
            "pass": sorted(k for k, r in rows.items() if r["verdict"] == "PASS"),
            "rows": rows}


def write(doc: dict[str, Any], path: Path | None = None) -> None:
    path = path or REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)

