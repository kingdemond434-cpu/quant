"""Adapters for mechanisms whose observable genuinely IS in the bars -- and the ones where it isn't.

WHY THESE EXIST (2026-08-30)

The hourly loop resolved three compiled cells and reported `no adapter registered for
'session_transition'` and `'liquidity_shock'`. Both are measurable -- `session_transition` is
DIRECT, its clock comes from the bar index and nothing stands in for anything -- they simply had
no adapter, so the registry correctly refused rather than guessing.

That is the registry working. It is also five mechanisms the desk could measure and was not.

HONESTY IS THE ONLY THING THAT MAKES THIS FILE WORTH HAVING. A bar-derived adapter is trivial to
write and trivially tempting to over-claim: every one of these could be labelled DIRECT and the
code would run identically. The classes below are argued, not asserted, and three of the five are
HEURISTIC on purpose:

    session_transition   DIRECT       the session clock IS the bar index; the displacement IS
                                      the claim's quantity
    volatility_shock     DIRECT       range relative to its own history IS realised volatility
    liquidity_shock      HEURISTIC    range widens in thin markets AND in fast ones. It cannot
                                      separate them, so a result here does not identify
                                      liquidity as the cause. Spread or depth would; the desk has
                                      a per-hour spread surface and this adapter uses it when it
                                      is present, which is what lifts it to VALIDATED.
    inventory_rebalance  HEURISTIC    distance from a mean is consistent with inventory pressure
                                      and with twenty other things
    forced_deleveraging  HEURISTIC    an ATR-scaled move is what forced selling looks like, and
                                      also what ordinary news looks like

Labelling the last three DIRECT would let a negative result bury a real mechanism, which is the
exact failure `failure_states` exists to prevent. A HEURISTIC adapter still RUNS -- exploration is
cheap -- its result just may not be read as evidence about the mechanism it is named after.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from libs.research_os.adapters.base import MeasurementResult, ResearchAdapter

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"

#: Broker hours (Fusion runs UTC+3). The bars are on this clock, so the windows are too.
_SESSIONS: dict[str, tuple[int, int]] = {
    "asia": (1, 9), "london": (9, 17), "new_york": (15, 23), "overlap": (15, 17),
}


def _rng(d: pd.DataFrame) -> pd.Series:
    return d["high"] - d["low"]


def _atr(d: pd.DataFrame, n: int = 20) -> pd.Series:
    prev = d["close"].shift(1)
    tr = pd.concat([_rng(d), (d["high"] - prev).abs(), (d["low"] - prev).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(n).mean()


class SessionTransitionAdapter(ResearchAdapter):
    """Displacement inside a named session. DIRECT: the clock is the index."""

    mechanism = "session_transition"
    requires = ()

    def compatibility(self, spec: dict[str, Any]) -> float:
        return 1.0

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        session = str(spec.get("context") or spec.get("session") or "asia")
        window = _SESSIONS.get(session)
        if window is None:
            # REFUSE AN UNKNOWN SESSION. Defaulting to Asia would run the experiment in a session
            # the hypothesis never named and file the answer against a claim nobody made.
            return MeasurementResult(
                status="UNAVAILABLE", adapter="SessionTransitionAdapter",
                notes=(f"session {session!r} is not a named window {sorted(_SESSIONS)}; refusing "
                       f"rather than defaulting, because a default answers a different question"))
        lo, hi = window
        h = bars.index.hour
        mask = (h >= lo) & (h < hi)
        day = bars.index.floor("D")
        base = bars["close"].where(h == lo).groupby(day).transform("first")
        disp = ((bars["close"] / base) - 1.0).where(mask)
        return MeasurementResult(
            status="DIRECT", adapter="SessionTransitionAdapter",
            feature_ids=[f"session_disp:{session}"], confidence=1.0, pit_safe=True,
            series=disp,
            notes=(f"displacement from the {session} open, masked to broker hours {lo}-{hi}. The "
                   f"session clock comes from the bar index and the displacement is the "
                   f"quantity the claim is about -- nothing stands in for anything."))


class VolatilityShockAdapter(ResearchAdapter):
    """Realised volatility against its own history. DIRECT at bar resolution."""

    mechanism = "volatility_shock"
    requires = ()

    def compatibility(self, spec: dict[str, Any]) -> float:
        return 1.0

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        n = int(spec.get("vol_n", 20))
        r = _rng(bars)
        z = (r - r.rolling(n * 5, min_periods=n).mean()) / r.rolling(n * 5, min_periods=n).std()
        return MeasurementResult(
            status="DIRECT", adapter="VolatilityShockAdapter",
            feature_ids=[f"range_z_{n}"], confidence=1.0, pit_safe=True, series=z,
            notes=("bar range z-scored against its own trailing history. Range IS a realised "
                   "volatility measure at bar resolution; this is the observable, not a proxy."))


class LiquidityAdapter(ResearchAdapter):
    """Spread when the surface exists, range when it does not -- and it says which."""

    mechanism = "liquidity_shock"
    requires = ("desks/mt5/data/cost_surface.json",)

    def compatibility(self, spec: dict[str, Any]) -> float:
        # Always usable, but BETTER with the spread surface. Compatibility reflects that rather
        # than pretending the two are equivalent.
        return 1.0 if (DESK / "data" / "cost_surface.json").exists() else 0.6

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        sym = str(spec.get("symbol") or "")
        surface = DESK / "data" / "cost_surface.json"
        if surface.exists() and sym:
            try:
                blob = json.loads(surface.read_text("utf-8"))
                per_hour = ((blob.get("symbols") or blob).get(sym) or {}).get("by_hour") or {}
            except (OSError, json.JSONDecodeError, AttributeError):
                per_hour = {}
            if per_hour:
                # SPREAD IS THE ACTUAL OBSERVABLE the mechanism names, and it varies by hour --
                # which is the whole reason the surface exists.
                vals = bars.index.hour.map(lambda h: per_hour.get(str(h)))
                s = pd.Series(pd.to_numeric(pd.Series(vals, index=bars.index), errors="coerce"))
                if s.notna().sum() > len(s) * 0.5:
                    z = (s - s.rolling(200, min_periods=40).mean()) / \
                        s.rolling(200, min_periods=40).std()
                    return MeasurementResult(
                        status="VALIDATED_PROXY", adapter="LiquidityAdapter",
                        feature_ids=[f"spread_z:{sym}"], confidence=0.9, pit_safe=True,
                        series=z,
                        notes=("per-hour spread from the cost surface, z-scored. Spread is the "
                               "observable the mechanism names; VALIDATED rather than DIRECT "
                               "because the surface is a periodic measurement, not a tick feed."))

        r = _rng(bars)
        z = r / r.rolling(200, min_periods=40).median()
        return MeasurementResult(
            status="HEURISTIC_PROXY", adapter="LiquidityAdapter",
            feature_ids=["range_over_median"], confidence=0.5, pit_safe=True, series=z,
            notes=("no per-hour spread for this symbol, so range/median stands in. HEURISTIC: "
                   "range widens in thin markets AND in fast ones and cannot separate them, so a "
                   "result here does not identify liquidity as the cause. May explore; may not "
                   "be read as evidence about the liquidity mechanism."))


class InventoryAdapter(ResearchAdapter):
    """Distance from a mean as an inventory stand-in. Honestly heuristic."""

    mechanism = "inventory_rebalance"
    requires = ()

    def compatibility(self, spec: dict[str, Any]) -> float:
        return 0.6

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        n = int(spec.get("lookback", 20))
        s = (bars["close"] - bars["close"].rolling(n).mean()) / _atr(bars)
        return MeasurementResult(
            status="HEURISTIC_PROXY", adapter="InventoryAdapter",
            feature_ids=[f"mean_dist_atr_{n}"], confidence=0.5, pit_safe=True, series=s,
            notes=("ATR-scaled distance from a rolling mean. HEURISTIC: this is consistent with "
                   "dealer inventory pressure and with twenty other things, and identifies none "
                   "of them. Real inventory would need flow or positioning data."))


class ForcedLiquidationAdapter(ResearchAdapter):
    """ATR-scaled displacement as a forced-selling stand-in. Honestly heuristic."""

    mechanism = "forced_deleveraging"
    requires = ()

    def compatibility(self, spec: dict[str, Any]) -> float:
        return 0.6

    def measure(self, spec: dict[str, Any], bars: pd.DataFrame) -> MeasurementResult:
        s = bars["close"].diff() / _atr(bars)
        return MeasurementResult(
            status="HEURISTIC_PROXY", adapter="ForcedLiquidationAdapter",
            feature_ids=["ret_over_atr"], confidence=0.5, pit_safe=True, series=s,
            notes=("bar return scaled by ATR. HEURISTIC: a large ATR-scaled move is what forced "
                   "selling looks like and also what ordinary news looks like. Margin "
                   "utilisation or liquidation prints would separate them."))
