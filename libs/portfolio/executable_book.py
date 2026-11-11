"""THE BOOK THE VENUE WILL ACTUALLY HOLD, SCORED AGAINST THE BOOK THE SOLVER ASKED FOR.

ALLOC-05/06/15/17/18/23 (backlog 2026-10-07). `pf_allocator` solves per-sleeve HEAT on a
continuum. The gateway turns heat into lots with `mt5desk.sizing.risk_lot`: target risk over
per-lot stop risk, rounded DOWN to the venue step, and -- under allocator sovereignty, the
default since #53 -- a target below the venue minimum sends nothing. So the book the account
carries is not the book the solver scored, and until this module nobody measured the gap.

What it measures, all as REPORTS (it sizes nothing and nothing reads it for sizing):

  * continuous vs executable lots and heat, per sleeve, with the reason a sleeve lost size
    (step residue, below-minimum, unpriced);
  * the growth both books earn on the same daily R matrix -- the price of discreteness in
    E[log W] per day, which is the number that says whether rounding is a defect worth fixing
    (by netting, or by moving heat to sleeves whose lot grid is finer);
  * the five quantities ALLOC-15 asks to be kept apart: equity allocation (share of book heat),
    stop-risk heat, risk budget (the solver's target), notional exposure and margin usage;
  * per-symbol net vs gross lots through `libs.portfolio.netting`, with attribution kept;
  * heat RESERVED by resting and pending orders (an OCO pair reserves its worse leg, not both),
    so the free heat the next solve sees is honest (ALLOC-17/23);
  * whether each sleeve's symbol is inside its trading session now (ALLOC-18/23), via the
    venue's own rule rows in `libs.research.market_constitution`;
  * per-sleeve measured turnover cost in R next to the desk-wide constant (ALLOC-06).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

#: The floor below which a book's daily return is clipped before the log. It is the ruin
#: boundary of a 1-equity account (a -100% day), moved in by 1e-9 so log() stays finite; it never
#: binds on a book whose heat is under 1, which every book this desk can solve is.
RUIN_EPS = 1e-9
#: Float-representation repair for the venue step (same value and reason as
#: `libs.portfolio.netting._STEP_EPS`): derived as nine orders of magnitude below a 0.01 step.
STEP_EPS = 1e-9


@dataclass(frozen=True)
class SleeveSpec:
    """What it takes to turn one sleeve's heat into lots on one venue."""

    name: str
    symbol: str
    side: float                       # +1 long-biased, -1 short-biased, 0 two-sided/unknown
    stop_dist: float | None           # price units
    tick_value: float | None          # account currency per tick per lot
    tick_size: float | None
    volume_min: float | None
    volume_step: float | None
    contract_size: float | None = None
    price: float | None = None
    asset_class: str = ""

    def risk_per_lot(self) -> float | None:
        vals = (self.stop_dist, self.tick_value, self.tick_size)
        if any(v is None or not math.isfinite(float(v)) or float(v) <= 0 for v in vals):
            return None
        return float(self.stop_dist) * float(self.tick_value) / float(self.tick_size)  # type: ignore[arg-type]


def executable(heat: float, equity: float, spec: SleeveSpec) -> dict[str, Any]:
    """One sleeve: the lots the solver's heat implies, the lots the venue takes, and why."""
    rpl = spec.risk_per_lot()
    out: dict[str, Any] = {"heat_target": float(heat), "symbol": spec.symbol}
    if heat <= 0:
        return {**out, "lots_continuous": 0.0, "lots_executable": 0.0, "heat_executable": 0.0,
                "status": "ZERO_TARGET"}
    step, vmin = spec.volume_step, spec.volume_min
    if rpl is None or equity <= 0 or not step or step <= 0 or not vmin or vmin <= 0:
        return {**out, "lots_continuous": None, "lots_executable": None, "heat_executable": None,
                "status": "UNPRICED",
                "why": "no stop distance, tick economics, venue step/minimum or equity"}
    raw = heat * equity / rpl
    lots = round(math.floor(raw / step + STEP_EPS) * step, 8)
    status = "EXACT" if abs(lots - raw) < step * 1e-6 else "STEP_RESIDUE"
    if lots < vmin:
        lots, status = 0.0, "BELOW_MINIMUM"
    return {**out, "lots_continuous": round(raw, 6), "lots_executable": lots,
            "heat_executable": round(lots * rpl / equity, 8), "status": status,
            "min_lot_heat": round(vmin * rpl / equity, 8)}


def log_growth(r: np.ndarray, h: np.ndarray) -> float:
    """Mean daily log growth of a heat vector `h` on an R-multiple day matrix `r` (T x n)."""
    if r.size == 0 or h.size == 0:
        return float("nan")
    port = np.nan_to_num(r, nan=0.0) @ h
    return float(np.mean(np.log(np.maximum(1.0 + port, RUIN_EPS))))


def growth_gap(r: np.ndarray, names: Sequence[str], continuous: Mapping[str, float],
               executed: Mapping[str, float]) -> dict[str, Any]:
    """E[log W]/day of the continuous book vs the executable one, on the same days."""
    if r.ndim != 2 or r.shape[1] != len(names) or r.shape[0] < 2:
        return {"status": "UNMEASURED", "why": "no common daily R matrix"}
    hc = np.array([float(continuous.get(n, 0.0)) for n in names])
    he = np.array([float(executed.get(n, 0.0)) for n in names])
    gc, ge = log_growth(r, hc), log_growth(r, he)
    return {"status": "MEASURED", "n_days": int(r.shape[0]), "n_sleeves": len(names),
            "elog_per_day_continuous": round(gc, 8), "elog_per_day_executable": round(ge, 8),
            "discreteness_cost_per_day": round(gc - ge, 8),
            "discreteness_cost_annual": round((gc - ge) * 252, 6),
            "heat_continuous": round(float(hc.sum()), 6),
            "heat_executable": round(float(he.sum()), 6)}


def labelled_exposures(rows: Mapping[str, Mapping[str, Any]], specs: Mapping[str, SleeveSpec],
                       equity: float, margin_used: float | None) -> dict[str, Any]:
    """ALLOC-15: five quantities, never one number wearing five names."""
    total_exec = sum(float(r.get("heat_executable") or 0.0) for r in rows.values())
    per: dict[str, dict[str, Any]] = {}
    notional_total = 0.0
    n_notional = 0
    for name, r in rows.items():
        spec = specs.get(name)
        lots = r.get("lots_executable")
        notional = None
        if (spec is not None and isinstance(lots, (int, float)) and spec.contract_size
                and spec.price and equity > 0):
            notional = float(lots) * float(spec.contract_size) * float(spec.price)
            if spec.tick_value and spec.tick_size:
                # Quote -> account conversion from the broker's own tick economics: one tick
                # of price on one contract unit is worth tick_value / (tick_size * contract).
                notional *= float(spec.tick_value) / (float(spec.tick_size)
                                                      * float(spec.contract_size))
            notional_total += notional
            n_notional += 1
        hx = float(r.get("heat_executable") or 0.0)
        per[name] = {
            "risk_budget": round(float(r.get("heat_target") or 0.0), 8),
            "stop_risk_heat": round(hx, 8),
            "equity_allocation": round(hx / total_exec, 6) if total_exec > 0 else 0.0,
            "notional_exposure": (round(notional / equity, 6) if notional is not None
                                  else None),
        }
    return {
        "per_sleeve": per,
        "total": {
            "risk_budget": round(sum(float(r.get("heat_target") or 0.0)
                                     for r in rows.values()), 8),
            "stop_risk_heat": round(total_exec, 8),
            "notional_exposure": (round(notional_total / equity, 6)
                                  if n_notional and equity > 0 else None),
            "n_notional_measured": n_notional,
            "margin_usage": (round(float(margin_used) / equity, 6)
                             if margin_used is not None and equity > 0 else None),
        },
        "definitions": {
            "risk_budget": "the heat the solver asked for (fraction of equity at the stop)",
            "stop_risk_heat": "the heat the venue's lot grid lets the account actually carry",
            "equity_allocation": "this sleeve's share of the executable book's heat",
            "notional_exposure": "lots x contract x price in account currency, over equity",
            "margin_usage": "broker margin in use over equity (account-level only)",
        },
    }


def reserved_heat(orders: Sequence[Mapping[str, Any]], tick: Mapping[str, tuple[float, float]],
                  equity: float) -> dict[str, Any]:
    """Heat held by resting/pending orders. Orders sharing a `group` (an OCO bracket) reserve
    only their worst leg, since at most one can fill; ungrouped orders each reserve their own."""
    if equity <= 0:
        return {"status": "UNMEASURED", "why": "no equity", "reserved_heat": None}
    groups: dict[str, float] = {}
    unpriced: list[str] = []
    for i, o in enumerate(orders):
        sym = str(o.get("symbol") or "")
        try:
            lots, price, sl = float(o["lots"]), float(o["price"]), float(o["sl"])
        except (KeyError, TypeError, ValueError):
            unpriced.append(f"{sym or i}: no lots/price/sl")
            continue
        tv_ts = tick.get(sym)
        if tv_ts is None or tv_ts[1] <= 0:
            unpriced.append(f"{sym}: no tick economics")
            continue
        risk = abs(price - sl) * lots * tv_ts[0] / tv_ts[1] / equity
        g = str(o.get("group") or f"_solo{i}")
        groups[g] = max(groups.get(g, 0.0), risk)
    return {"status": "MEASURED" if not unpriced else ("PARTIAL" if groups else "UNMEASURED"),
            "reserved_heat": round(sum(groups.values()), 8), "n_groups": len(groups),
            "unpriced": unpriced}


def bracket_orders(state: Mapping[str, Any], symbol_of: Mapping[str, str]) -> list[dict[str, Any]]:
    """Resting bracket legs from `gateway_state.json` that the venue accepted and are unfilled.

    A leg is resting when its result row carries a success retcode (10008 placed / 10009 done)
    and the bracket has no fill recorded; a blocked or refused leg reserves nothing.
    """
    out: list[dict[str, Any]] = []
    for window, b in (state.get("brackets") or {}).items():
        if not isinstance(b, Mapping) or b.get("filled") or b.get("cancelled"):
            continue
        spec = b.get("spec") or {}
        res = {str(r.get("side")): r for r in ((b.get("result") or {}).get("orders") or [])
               if isinstance(r, Mapping)}
        for side, leg in spec.items():
            r = res.get(str(side)) or {}
            if r.get("retcode") not in (10008, 10009) or r.get("blocked"):
                continue
            out.append({"symbol": symbol_of.get(str(window), b.get("symbol") or ""),
                        "lots": b.get("lot"), "price": (leg or {}).get("price"),
                        "sl": (leg or {}).get("sl"), "group": f"bracket:{window}"})
    pend = state.get("pending")
    if isinstance(pend, list):
        out.extend(dict(p) for p in pend if isinstance(p, Mapping))
    elif isinstance(pend, Mapping):
        out.append(dict(pend))
    return out


def session_states(specs: Mapping[str, SleeveSpec], venue: Any, ts: Any,
                   class_of: Any, state_at: Any) -> dict[str, Any]:
    """Per sleeve: is its symbol's instrument class inside a CONTINUOUS session at `ts`?"""
    per: dict[str, str] = {}
    for name, spec in specs.items():
        cls = class_of(spec.asset_class)
        if not cls:
            per[name] = "UNCLASSIFIED"
            continue
        try:
            per[name] = str(state_at(venue, ts, cls).session_state)
        except Exception as exc:
            per[name] = f"UNMEASURED ({type(exc).__name__})"
    closed = sorted(n for n, s in per.items() if s not in ("CONTINUOUS",)
                    and not s.startswith("UNMEASURED") and s != "UNCLASSIFIED")
    return {"per_sleeve": per, "n_outside_session": len(closed), "outside_session": closed[:50]}
