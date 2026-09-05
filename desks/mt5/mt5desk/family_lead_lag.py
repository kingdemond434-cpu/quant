"""Trade the laggard after the leader moved: an edge from the cross-asset information graph.

    signal_t = z( sum of the driver's log returns over the last `lag` bars )
    side     = sign(signal) x direction       when |signal| >= entry_z

`libs.research.lead_lag.edge` measures, for a (driver, target) pair, the lag at which the
driver's past return carries information about the target's next return, its sign, and whether
that information is forecast value out of sample. This family executes exactly that claim on
the target's bars with the driver's bars supplied by `family_inputs` (the driver is named on
the recipe as `driver_symbol`, never re-chosen here). The z-normalisation is over the driver's
own trailing window so the threshold means the same thing on gold and on a JPY cross.

REFUSES without driver bars, and refuses a driver that is the target itself.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

DIRECTIONS = ("same", "opposite")


def family_lead_lag(
    df: pd.DataFrame,
    *,
    driver: pd.DataFrame | None = None,
    driver_symbol: str = "",
    lag: int = 2,
    direction: str = "same",
    entry_z: float = 1.5,
    norm: int = 240,
    hold_bars: int = 6,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    if driver is None or direction not in DIRECTIONS or "close" not in driver.columns:
        return []
    d = _h1(df)
    if len(d) < max(2 * norm, 300):
        return []
    dc = driver["close"].astype(float)
    dc.index = pd.DatetimeIndex(pd.to_datetime(dc.index, utc=True, errors="coerce"))
    dc = dc[~dc.index.duplicated(keep="last")].sort_index()
    if dc.index.equals(d.index) and np.allclose(dc.to_numpy(), d["close"].to_numpy()):
        return []                                             # the driver is the target
    x = np.log(dc).diff().reindex(d.index).fillna(0.0)
    sig = x.rolling(int(lag), min_periods=int(lag)).sum()
    r = sig.rolling(int(norm), min_periods=int(norm))
    z = ((sig - r.mean()) / r.std()).to_numpy(dtype=float)
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    idx = d.index
    flip = 1 if direction == "same" else -1
    out: list[Signal] = []
    last = -10 ** 9
    for i in range(int(norm), len(idx) - 1):
        if i - last < int(hold_bars):
            continue
        zi, a = z[i], atr[i]
        if not np.isfinite(zi) or abs(zi) < float(entry_z) or not np.isfinite(a) or a <= 0:
            continue
        side = int(np.sign(zi)) * flip
        if side == 0:
            continue
        px = close[i]
        out.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                          tag=f"lead_lag:{driver_symbol or 'driver'}:{direction}",
                          trigger=None, wait_bars=1))
        last = i
    return out
