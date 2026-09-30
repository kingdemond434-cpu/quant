"""DATASET STANCE: the DIRECT use of any dataset the desk holds -- its reading alone picks the side.

THE PRINCIPAL, 2026-09-30: "all datasets must be exploited ... not just stored like museum items
always" -- every enrolled dataset feeds (a) direct cells, (b) conditioners and (c) allocation
intelligence. `family_dataset_conditioned` is (b) for every kind of dataset. `exogenous_conditioner`
is (a) -- but only for a lake pack (`data/lake/series/<pack>.parquet`); a CFTC file or an
intelligence seat had no direct family at all, so the only thing it could ever do was condition
somebody else's entry. This is the missing (a): the same stance `exogenous_conditioner` takes, read
through the ONE loader every dataset kind shares (`mt5desk.dataset_series`), so lake, cot and intel
datasets are all direct-usable and the lake still has exactly one reader.

WHAT A CELL IS. `(dataset, field, match, transform, threshold, side_when_high)`: while the
dataset's lagged, transformed reading is beyond `threshold`, take `side_when_high` when it is high
and the opposite when it is low; ATR stop and target like `exogenous_conditioner`. Identity is the
whole tuple, and the cell is charged to the census like any other trial.

THE JOIN is `dataset_series.conditioned` -> `on_bars`: lagged a full publication day on its own
availability clock, then read strictly before each bar opens, so the broker clock's offset from
UTC cannot produce a lookahead stance.

REFUSES -- returns no signals -- when the dataset, the field or its stamp is absent, or it carries
fewer than MIN_OBSERVATIONS readings: UNMEASURED, never a price-only fall-back.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from mt5desk.dataset_series import DEFAULT_LAG_HOURS, DEFAULT_Z_WINDOW, conditioned, on_bars
from mt5desk.families import Signal, _atr, _h1

MIN_OBSERVATIONS = 30


def family_dataset_stance(
    df: pd.DataFrame,
    *,
    dataset: str,
    field: str,
    match: str = "",
    transform: str = "level_z",
    threshold: float = 1.0,
    side_when_high: int = 1,
    lag_hours: int = DEFAULT_LAG_HOURS,
    z_window: int = DEFAULT_Z_WINDOW,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 2.0,
    ttl_bars: int = 96,
    series_root: Path | None = None,
) -> list[Signal]:
    """A directional stance while `dataset.field` sits beyond `threshold`, on its own clock."""
    series = conditioned(str(dataset), str(field), transform=str(transform), match=str(match),
                         lag_hours=int(lag_hours), z_window=int(z_window), root=series_root)
    if series is None or len(series) < MIN_OBSERVATIONS:
        return []
    d = _h1(df)
    if d.empty:
        return []
    try:
        m = on_bars(series, pd.DatetimeIndex(d.index))
    except (TypeError, ValueError):
        return []
    atr = _atr(d, atr_n).to_numpy()
    close = d["close"].to_numpy()
    thr = abs(float(threshold))
    sgn = 1 if int(side_when_high) >= 0 else -1
    out: list[Signal] = []
    for i in range(atr_n, len(d) - 1):
        mv = m[i]
        if not np.isfinite(mv) or abs(float(mv)) <= thr:
            continue
        a = float(atr[i])
        if not np.isfinite(a) or a <= 0:
            continue
        side = sgn if float(mv) > 0 else -sgn
        px = float(close[i])
        out.append(Signal(time=d.index[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(ttl_bars),
                          tag="dataset_stance", trigger=None, wait_bars=1))
    return out
