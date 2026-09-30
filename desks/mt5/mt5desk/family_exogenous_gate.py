"""EXOGENOUS GATE -- an existing price family, taken only inside an information regime.

THE PRINCIPAL'S ORDER (2026-09-30): every dataset feeds INDIRECT cells too -- a regime feature
used as a CONDITION on existing families. `exogenous_conditioner` bets on the series directly
(side from the sign of its extreme); nothing let a series decide WHEN an already-registered
mechanism is allowed to fire. This operator does: it rebuilds `base_family`'s own signals from
bars and params, exactly as `family_exit_operated` does, and keeps only those whose bar sits in
the gated state of a lake series -- the disclosure flow in a burst, a revision balance at a low.

THE QUESTION IS DIFFERENT FROM THE BASE CELL'S, which is why it earns its own trial. The base
cell asks "does this mechanism pay"; the gated cell asks "does it pay DIFFERENTLY when this
country's primary disclosures are unusually heavy". The un-gated base is the control arm and is
already an ordinary candidate in the docket.

POINT IN TIME is `family_exogenous_conditioner.conditioner`'s: the series is read on its own
`available_time` clock and held back `lag_hours` before any alignment, so the broker clock's two-
to-three-hour offset from UTC cannot produce a look-ahead join. Nothing is reimplemented here.

REFUSES -- returns [] -- when the base family cannot be rebuilt from bars and params alone
(`family_exit_operated._UNWRAPPABLE`), when the series, its column or its stamp is absent, when
the history is thinner than the conditioner's own minimum, or when the gate is unknown.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _h1, get_family_func

GATES: tuple[str, ...] = ("high", "low", "extreme", "calm")


def _in_gate(value: float, gate: str, threshold: float) -> bool:
    if not np.isfinite(value):
        return False
    t = abs(float(threshold))
    if gate == "high":
        return value >= t
    if gate == "low":
        return value <= -t
    if gate == "extreme":
        return abs(value) >= t
    return abs(value) < t                                   # calm


def family_exogenous_gate(
    df: pd.DataFrame,
    *,
    base_family: str = "",
    base_params: dict[str, Any] | None = None,
    source: str = "",
    signal: str = "",
    transform: str = "level_z",
    gate: str = "high",
    threshold: float = 1.0,
    lag_hours: int = 24,
    z_window: int = 250,
    series_root: Path | None = None,
) -> list[Signal]:
    """`base_family`'s signals on the bars where the exogenous series is in `gate`."""
    from mt5desk.family_exit_operated import _UNWRAPPABLE
    from mt5desk.family_exogenous_conditioner import MIN_OBSERVATIONS, conditioner

    if gate not in GATES or not base_family or base_family in _UNWRAPPABLE \
            or base_family in ("exogenous_gate", "exogenous_conditioner", "exit_operated"):
        return []
    fn = get_family_func(base_family)
    if fn is None:
        return []
    cond = conditioner(source, signal, transform, lag_hours=lag_hours, z_window=z_window,
                       root=series_root)
    if cond is None or len(cond) < MIN_OBSERVATIONS:
        return []
    d = _h1(df)
    if d.empty:
        return []
    params = {k: v for k, v in dict(base_params or {}).items() if k not in ("timeframe", "session")}
    try:
        raw = fn(d, **params)
    except Exception:
        return []
    sigs = [s for s in (raw or []) if isinstance(s, Signal)]
    if not sigs:
        return []
    try:
        m = cond.reindex(cond.index.union(d.index)).ffill().reindex(d.index)
    except (TypeError, ValueError):
        return []
    vals = m.to_numpy(dtype=float)
    pos = d.index.get_indexer([s.time for s in sigs])
    return [s for s, i in zip(sigs, pos, strict=True)
            if i >= 0 and _in_gate(float(vals[i]), gate, threshold)]
