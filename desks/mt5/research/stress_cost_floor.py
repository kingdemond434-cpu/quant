"""A COST STRESS THAT STRESSES: a nonzero basis for the 3x arm on zero-spread symbols.

THE DEFECT (audit 2026-09-30). `engine.Costs.from_symbol` stresses the SPREAD only
(`spread_per_lot = max(pts * tick * contract * mult, 0.05)`). Fusion Zero quotes 0 points on 14 FX
majors (AUDJPY AUDSGD AUDUSD EURAUD EURCAD EURGBP EURUSD GBPCAD GBPUSD NZDCAD NZDUSD USDCAD USDCHF
USDJPY in the registry, `median_spread_pts == 0`), so their 1x and 3x arms both charge the 0.05
floor plus commission: the "stress" costs nothing extra, and with noise the 3x arm can read better
than the 1x. The sealed gauntlet's `stress_costs` gate has passed cells on those symbols on that
basis.

THE BASIS, one function for every caller (`research/stage1_judge.py` imports it; the sealed patch
`/mnt/project-files/patches/gauntlet_zero_spread_stress.patch` imports the same function):

  * a registry spread > 0: unchanged -- `from_symbol(meta, mult)` exactly as today;
  * a registry spread of 0: the stress basis is the COST-TRUTH QUOTE (the terminal's own
    `live_spread_pts`, `data/cost_truth_quotes.json`) PLUS the round-turn commission expressed in
    points, or a DECLARED per-symbol floor (`DECLARED_FLOOR_PTS`) when that is larger; the 3x arm
    charges `mult x basis` as spread on top of the commission, so stress is strictly monotone;
  * nothing measured (no quote, no commission conversion, no declared floor): None. FAIL CLOSED --
    a stress with no basis cannot pass.

The 1x arm is never changed: a measured zero spread plus commission is the true cost; only the
stress arm needed a basis to multiply.

THE FILL-HOUR SPREAD IS THE BASIS WHEN IT IS MEASURED (audit PR143_v3, 2026-09-30). The sealed 1x
arm charges the spread of the hour the cell FILLS in (`cost_surface.json`, `build_cell`), but the
3x arm multiplied the registry number -- for the majors the commission-only basis above. Measured:
EURUSD's fill-hour spread is 12 pts and its commission basis ~4.6 pts, so the "3x" arm charged
~13.8 pts, 1.16x the fill-hour spread the 1x arm already paid. And on a spread symbol whose fill
hour is thin (EURZAR: 1,918 pts at hour 01 against a 310 pooled median) the 3x arm charged LESS
than the 1x arm. So, for EVERY symbol, when the caller names the fill hour and the surface has it
MEASURED, the stress arm charges `mult x max(fill-hour spread, registry spread)`: three times what
the 1x arm pays, never below the registry stress it replaces (a tightening only). With no measured
fill hour, the rules above apply unchanged, fail-closed branch included.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
COST_TRUTH_QUOTES = DESK / "data" / "cost_truth_quotes.json"
COST_SURFACE = DESK / "data" / "cost_surface.json"
#: Declared per-symbol floors in POINTS, for a symbol whose quote and commission are both
#: unmeasured. Empty by default: an undeclared, unmeasured symbol fails closed.
DECLARED_FLOOR_PTS: dict[str, float] = {}


def load_quotes(path: Path | None = None) -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(Path(path or COST_TRUTH_QUOTES).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    sy = doc.get("symbols") if isinstance(doc, dict) else None
    return sy if isinstance(sy, dict) else {}


def _commission_default() -> float:
    import inspect

    from mt5desk.engine import Costs
    return float(inspect.signature(Costs.from_symbol).parameters["commission_per_lot"].default)


def is_zero_spread(meta_row: dict[str, Any]) -> bool:
    try:
        return float(meta_row.get("median_spread_pts", 0.0) or 0.0) <= 0.0
    except (TypeError, ValueError):
        return True


def stress_basis_pts(sym: str, meta_row: dict[str, Any],
                     quotes: dict[str, dict[str, Any]] | None = None,
                     commission_per_lot: float | None = None
                     ) -> tuple[float | None, dict[str, Any]]:
    """(points, how) for a zero-spread symbol's stress basis; (None, why) when unmeasured."""
    q = (load_quotes() if quotes is None else quotes).get(sym) or {}
    how: dict[str, Any] = {"symbol": sym}
    quote = q.get("live_spread_pts")
    try:
        quote_pts = float(quote) if quote is not None else None
    except (TypeError, ValueError):
        quote_pts = None
    how["quote_pts"] = quote_pts
    cs = float(meta_row.get("contract_size", 0.0) or 0.0)
    ts = float(meta_row.get("tick_size", 0.0) or 0.0)
    tv = float(meta_row.get("tick_value", 0.0) or 0.0)
    comm = _commission_default() if commission_per_lot is None else float(commission_per_lot)
    comm_pts = None
    if cs > 0 and ts > 0 and tv > 0 and comm > 0:
        # account currency per lot -> price units per lot (x cs*ts/tv) -> points (/ ts*cs):
        # one commission side is comm / tv points; a round turn is two sides.
        comm_pts = 2.0 * comm / tv
    how["commission_round_turn_pts"] = comm_pts
    measured = (quote_pts or 0.0) + (comm_pts or 0.0) if (
        quote_pts is not None or comm_pts is not None) else None
    declared = DECLARED_FLOOR_PTS.get(sym)
    how["declared_floor_pts"] = declared
    cands = [x for x in (measured, declared) if x is not None and math.isfinite(x) and x > 0]
    if not cands:
        how["status"] = "UNMEASURED"
        how["why"] = (f"{sym}: registry spread 0, no cost-truth quote, no commission conversion "
                      "(tick_value) and no declared floor -- the stress has no basis")
        return None, how
    pts = max(cands)
    how.update(status="MEASURED", basis_pts=pts,
               basis=("declared_floor" if declared is not None and pts == declared
                      else "cost_truth_quote_plus_commission"))
    return pts, how


_SURFACE: list[Any] = []


def load_surface(path: Path | None = None) -> dict[str, Any] | None:
    """`data/cost_surface.json`, loaded once per process (None when absent or unreadable)."""
    if path is None and _SURFACE:
        return _SURFACE[0]
    try:
        doc = json.loads(Path(path or COST_SURFACE).read_text("utf-8"))
        doc = doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        doc = None
    if path is None:
        _SURFACE.append(doc)
    return doc


def fill_hour_spread_pts(sym: str, hour: int | None,
                         surface: dict[str, Any] | None = None) -> float | None:
    """The MEASURED spread (points, p50) at the cell's fill hour, or None when unknown."""
    if hour is None:
        return None
    surf = load_surface() if surface is None else surface
    if not surf:
        return None
    try:
        from research.cost_surface import spread_pts
        v = spread_pts(surf, sym, int(hour))
    except Exception:
        return None
    return float(v) if v is not None and math.isfinite(float(v)) and float(v) > 0 else None


def stress_costs_for(sym: str, meta: dict[str, Any], mult: float, *,
                     quotes: dict[str, dict[str, Any]] | None = None,
                     hour: int | None = None,
                     surface: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
    """(Costs | None, how). mult <= 1: exactly `from_symbol(row, mult)`. Under stress with a
    MEASURED fill-hour spread (any symbol): `mult x max(fill-hour, registry spread)`. Otherwise a
    registry spread > 0 is `from_symbol(row, mult)`, and a zero-spread symbol's spread arm is
    `mult x basis`; None when nothing is measured (fail closed)."""
    from mt5desk.engine import Costs
    row = meta.get(sym, {}) if isinstance(meta, dict) else {}
    if float(mult) <= 1.0:
        return Costs.from_symbol(row, mult=mult), {"symbol": sym, "basis": "registry"}
    fill = fill_hour_spread_pts(sym, hour, surface)
    if fill is not None:
        try:
            reg = float(row.get("median_spread_pts", 0.0) or 0.0)
        except (TypeError, ValueError):
            reg = 0.0
        pts = max(fill, reg)
        return Costs.from_symbol(row, mult=mult, spread_pts=pts), {
            "symbol": sym, "status": "MEASURED", "basis": f"fill_hour_{int(hour):02d}_spread",  # type: ignore[arg-type]
            "fill_hour_spread_pts": fill, "registry_spread_pts": reg, "basis_pts": pts}
    if not is_zero_spread(row):
        return Costs.from_symbol(row, mult=mult), {"symbol": sym, "basis": "registry"}
    pts, how = stress_basis_pts(sym, row, quotes)
    if pts is None:
        return None, how
    return Costs.from_symbol(row, mult=mult, spread_pts=pts), how
