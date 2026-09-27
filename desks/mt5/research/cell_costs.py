"""ONE COST CONSTRUCTOR FOR A CELL, SHARED BY THE CERTIFICATE AND ITS FORWARD CLOCK.

MEASURED 2026-09-25, and three different prices were in use for one strategy:

    certificate, base arm   external_gauntlet.build_cell   FILL-HOUR spread, commission 2.00
    certificate, 3x arm     costs_for(mult=3)              POOLED median spread x3
    forward clock           shadow_forward.per_symbol_costs POOLED median spread, then the
                                                            FROZEN fields replaced it all --
                                                            commission 3.50 on rows frozen
                                                            before the correction

So a cell could be certified at one cost, stressed at a cheaper one, and forward-tested at a third.
Where the fill hour is the thin one (EURZAR fills at 1,918 pts against a 310 pooled median) the
forward clock was charging a sixth of what the certificate charged, and the evidence it accrued
was evidence about a cheaper strategy than the one certified.

This module is the one place the fill-hour price of a cell is built. `external_gauntlet` and
`shadow_forward` both call `fill_hour_costs`; the 3x arm is the same call with `mult=3`.
Commission is `libs.portfolio.fusion_cost.COMMISSION_PER_LOT_PER_SIDE` -- the account's measured
2.00 per lot per side -- and never a frozen or hard-coded figure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURFACE_PATH = DESK / "data" / "cost_surface.json"

_SURFACE: dict[str, Any] | None = None
_SURFACE_TRIED = False


def commission_per_side() -> float:
    """The account's measured commission, per lot per side, from its single source."""
    try:
        from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE
        return float(COMMISSION_PER_LOT_PER_SIDE)
    except Exception:                                   # pragma: no cover - import context
        return 2.00


def load_surface(path: Path | None = None, *, refresh: bool = False) -> dict[str, Any] | None:
    """The per-hour spread surface, loaded once. Absent is None -- the pooled median applies and
    the basis says so; it is never an invented number."""
    global _SURFACE, _SURFACE_TRIED
    if path is not None:
        try:
            doc = json.loads(Path(path).read_text("utf-8"))
        except (OSError, ValueError):
            return None
        return doc if isinstance(doc, dict) else None
    if refresh or not _SURFACE_TRIED:
        _SURFACE_TRIED = True
        try:
            doc = json.loads(SURFACE_PATH.read_text("utf-8"))
            _SURFACE = doc if isinstance(doc, dict) else None
        except (OSError, ValueError):
            _SURFACE = None
    return _SURFACE


def modal_fill_hour(sigs: Any, timeframe: str = "H1") -> int | None:
    """The broker hour a cell actually fills in, or None when it cannot be established.

    The signal time plus `wait_bars` is the fill bar, and `wait_bars` counts bars of the CELL'S
    OWN CHART (one hour on H1, five minutes on M5, a day on D1).
    """
    try:
        from mt5desk.universe_registry import timeframe_minutes
        minutes = int(timeframe_minutes(timeframe))
    except Exception:
        minutes = 60
    hours: dict[int, int] = {}
    for s in sigs or ():
        ts = getattr(s, "time", None)
        if ts is None:
            continue
        h = int(getattr(ts, "hour", -1))
        if h < 0:
            continue
        offset_minutes = int(getattr(ts, "minute", 0) or 0) + \
            int(getattr(s, "wait_bars", 0) or 0) * minutes
        h = (h + offset_minutes // 60) % 24
        hours[h] = hours.get(h, 0) + 1
    if not hours:
        return None
    return max(hours.items(), key=lambda kv: kv[1])[0]


def fill_hour_spread(sym: str, hour: int | None, surface: dict[str, Any] | None) -> float | None:
    """The measured spread (points) at `sym`'s fill hour, or None when the surface has none."""
    if surface is None or hour is None:
        return None
    try:
        from research.cost_surface import spread_pts
        val = spread_pts(surface, sym, hour)
    except Exception:
        return None
    return None if val is None else float(val)


def fill_hour_costs(meta_row: dict[str, Any], sym: str, *, hour: int | None,
                    surface: dict[str, Any] | None, mult: float = 1.0,
                    spread_pts: float | None = None) -> tuple[Any, str, float | None]:
    """(Costs, basis, spread_pts) for one cell at its fill hour, spread x`mult`.

    `spread_pts`, when given, is used as-is (the stress arm re-uses the base arm's spread so the
    two can never be priced on different books). Otherwise the surface's fill-hour spread is used
    when measured, else the registry's pooled median -- and the basis names which.
    """
    from mt5desk.engine import Costs
    spread = spread_pts if spread_pts is not None else fill_hour_spread(sym, hour, surface)
    basis = (f"fill_hour_{hour:02d}_spread" if (spread is not None and hour is not None)
             else "pooled_median_spread")
    costs = Costs.from_symbol(meta_row or {}, mult=mult,
                              commission_per_lot=commission_per_side(),
                              spread_pts=spread)
    return costs, basis, spread
