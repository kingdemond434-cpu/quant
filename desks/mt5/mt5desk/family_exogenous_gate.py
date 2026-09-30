"""EXOGENOUS GATE: an existing price-only cell, taken only while a published series is in a band.

WHY THIS EXISTS NEXT TO `family_exogenous_conditioner`. The conditioner is the DIRECT use of a
dataset: the series alone decides the side. Most of what the world publishes is weaker than that.
Weather over Iowa does not tell corn which way to go tomorrow, but a breakout on corn may be a
different trade when the growing-season temperature is two standard deviations high. That is a
CONDITIONING claim about an entry the desk already owns, and until this family existed it had no
cell shape: `macro_conditional` reads one fixed FRED file, and `exit_operated` operates on exits.
Every alt, macro-vintage and intelligence series therefore fed at most the direct family and was
never used as a regime filter on the ~40 price-only families that hold most of the docket.

WHAT A CELL IS. `(base_family, base_params)` names an ordinary price-only cell; `(source, signal,
transform, threshold, band)` names the gate. The base cell ungated is already an ordinary
candidate, so the control arm exists without this family manufacturing one, and the gated cell is
charged to the census like any other trial. Identity is the whole tuple.

THE JOIN IS THE CONDITIONER'S OWN, never a second implementation: the series is read through
`family_exogenous_conditioner.conditioner`, which lags it a publication day on its `available_time`
clock before any alignment, so the broker-clock offset cannot produce a lookahead gate.

WHAT IT REFUSES, loudly rather than as a silent zero:
  * a base family that cannot be rebuilt from bars and params alone (`family_exit_operated.
    wrappable`), or one of the operator families themselves;
  * a series that is absent, unstamped or too short -- UNMEASURED, never "no signal";
  * a gate that removes NOTHING -- that cell is the base cell again, a second multiplicity charge
    for no new question, so it returns [] exactly as `exit_operated` does for its identity case.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.build_memo import args_key, frame_fingerprint
from mt5desk.families import Signal, _h1, get_family_func
from mt5desk.family_exit_operated import _BASE_MEMO, wrappable
from mt5desk.family_exogenous_conditioner import (
    DEFAULT_LAG_HOURS,
    DEFAULT_Z_WINDOW,
    MIN_OBSERVATIONS,
    conditioner,
)

#: The four gates. `high`/`low` are one-sided extremes of the transformed series, `extreme` either
#: side, `calm` the middle -- the regime a mean-reversion base may only work in.
BANDS: tuple[str, ...] = ("high", "low", "extreme", "calm")

#: Families this wrapper never wraps: the operators (wrapping one would be an operator over an
#: operator whose identity nobody declared) and the direct family (gating a series on itself).
_NOT_A_BASE: frozenset[str] = frozenset({
    "exogenous_gate", "exogenous_conditioner", "exit_operated"})


def gateable(name: str) -> bool:
    """Can `name` be gated? Producers ask before minting, so no cell is minted to return []."""
    return bool(name) and name not in _NOT_A_BASE and wrappable(name)


def in_band(value: float, band: str, threshold: float) -> bool:
    thr = abs(float(threshold))
    if not np.isfinite(value):
        return False
    if band == "high":
        return value > thr
    if band == "low":
        return value < -thr
    if band == "extreme":
        return abs(value) > thr
    if band == "calm":
        return abs(value) <= thr
    return False


# NOT decorated with `register_family`, like `family_exogenous_conditioner`: a blind grid sweep has
# no base cell and no series to name, so it could only ever mint cells that return []. The cells
# are named by `research/world_cells.py`, which reads the published series and the base families.
def family_exogenous_gate(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    source: str = "",
    signal: str = "",
    transform: str = "level_z",
    threshold: float = 1.0,
    band: str = "high",
    lag_hours: int = DEFAULT_LAG_HOURS,
    z_window: int = DEFAULT_Z_WINDOW,
    series_root: Path | None = None,
) -> list[Signal]:
    """`base_family`'s own signals, kept only where the lagged series sits in `band`."""
    if not gateable(base_family) or band not in BANDS:
        return []
    cond = conditioner(source, signal, transform, lag_hours=lag_hours, z_window=z_window,
                       root=series_root)
    if cond is None or len(cond) < MIN_OBSERVATIONS:
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    params = dict(base_params or {})
    for k in ("timeframe", "session"):
        params.pop(k, None)
    d = _h1(df)
    if d.empty:
        return []

    def _base() -> list[Signal] | None:
        try:
            raw = fn(d, **params)
        except Exception:
            return None
        return [s for s in (raw or []) if isinstance(s, Signal)]

    sigs = _BASE_MEMO.get_or_compute(
        (frame_fingerprint(d), args_key(base_family, params)), _base)
    if not sigs:
        return []
    try:
        m = cond.reindex(cond.index.union(d.index)).ffill().reindex(d.index)
    except (TypeError, ValueError):
        return []
    kept: list[Signal] = []
    for s in sigs:
        try:
            v = m.get(s.time)
        except Exception:
            v = None
        if isinstance(v, pd.Series):
            v = v.iloc[-1] if len(v) else None
        if v is None:
            continue
        if in_band(float(v), band, threshold):
            kept.append(s)
    if len(kept) == len(sigs):
        return []          # the gate removed nothing: this is the base cell, already a candidate
    return kept
