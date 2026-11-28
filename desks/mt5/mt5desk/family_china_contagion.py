"""CHINA STRESS CONTAGION: trade an instrument the China knowledge graph says a Chinese stress
shock reaches, the morning after the shock shows up in the markets that price it first.

    stress_d  = mean over the stress sources s of  sign_s * r_s,d / sigma_s,d-1
                (daily UTC log return, scaled by its own causal EWMA vol; sources = USDCNH,
                CHINAH, HK50, XCUUSD from `libs.research.china_graph.stress_sources`, signed so
                that positive = China worse; the TARGET is always left out of its own index)
    S_d       = sum of stress over the last `window` days / sqrt(window)
    signal    at the first bar of day d+1 whose hour >= signal_hour, when |S_d| >= entry_z
    side      = sign(S_d) * exposure_sign * (+1 continuation | -1 reversal)

`exposure_sign` is the graph's signed response of THIS instrument's quoted price to a China
stress shock (AUDUSD -1, USDKRW +1); it rides on the recipe so every caller rebuilds the same
cell. `direction="same"` is the contagion hypothesis (the slower market catches up with the
shock); `"opposite"` is the overreaction hypothesis (the first day over-priced it). Both are
declared trials; the proposer charges every one.

Strictly causal: a day's stress is used only from the next day's `signal_hour` bar, and a
source's vol scale is the EWMA of returns BEFORE that day. REFUSES (returns []) when fewer than
`min_sources` source series can be read, when the target has no exposure sign, or when the
history is shorter than the vol warm-up.
"""
from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

_DESK = Path(__file__).resolve().parents[1]
DIRECTIONS = ("same", "opposite")
VOL_HALFLIFE_D = 20
WARMUP_D = 60


def _graph() -> Any:
    root = str(_DESK.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.research import china_graph
    return china_graph


def daily_close(df: pd.DataFrame) -> pd.Series:
    c = df["close"].astype(float)
    idx = pd.DatetimeIndex(pd.to_datetime(c.index, utc=True, errors="coerce"))
    c = pd.Series(c.to_numpy(), index=idx)
    c = c[~c.index.isna()]
    c = c[~c.index.duplicated(keep="last")].sort_index()
    return c.groupby(c.index.normalize()).last()


def stress_index(sources: Mapping[str, pd.DataFrame], signs: Mapping[str, int],
                 exclude: str = "", min_sources: int = 2) -> pd.DataFrame:
    """Daily (UTC date) stress: columns `stress` and `n_sources`. Causal vol scaling."""
    zs = {}
    for s, df in sources.items():
        if s == exclude or df is None or "close" not in df.columns or not signs.get(s):
            continue
        dc = daily_close(df)
        r = np.log(dc).diff()
        vol = r.ewm(halflife=VOL_HALFLIFE_D, min_periods=WARMUP_D // 2).std().shift(1)
        z = (r / vol).where(vol > 0) * int(signs[s])
        zs[s] = z
    if not zs:
        return pd.DataFrame(columns=["stress", "n_sources"])
    panel = pd.DataFrame(zs)
    n = panel.notna().sum(axis=1)
    out = pd.DataFrame({"stress": panel.mean(axis=1).where(n >= int(min_sources)),
                        "n_sources": n})
    return out


def family_china_stress_contagion(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    exposure_sign: int = 0,
    sources: Mapping[str, pd.DataFrame] | None = None,
    direction: str = "same",
    window: int = 1,
    entry_z: float = 1.5,
    min_sources: int = 2,
    signal_hour: int = 2,
    hold_bars: int = 24,
    atr_n: int = 20,
    stop_atr: float = 3.0,
    rr: float = 1.5,
) -> list[Signal]:
    if direction not in DIRECTIONS or int(exposure_sign) not in (-1, 1) or int(window) < 1:
        return []
    cg = _graph()
    signs = cg.stress_sources()
    frames: dict[str, pd.DataFrame] = dict(sources or {})
    if len(frames) < len(signs):
        from mt5desk.family_inputs import bars_named
        for s in signs:
            if s not in frames and s != symbol:
                f = bars_named(s, df)
                if f is not None:
                    frames[s] = f
    st = stress_index(frames, signs, exclude=symbol, min_sources=int(min_sources))
    if st.empty or st["stress"].notna().sum() < WARMUP_D:
        return []
    s_w = st["stress"].rolling(int(window), min_periods=int(window)).sum() / np.sqrt(int(window))
    d = _h1(df)
    if len(d) < 300:
        return []
    idx = d.index
    days = idx.normalize()
    # yesterday's (strictly earlier date's) stress, as known at each bar
    prev = s_w.reindex(s_w.index.union(days.unique())).ffill().shift(1)
    known = prev.reindex(days).to_numpy(dtype=float)
    hours = idx.hour
    atr = _atr(d, atr_n).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    flip = 1 if direction == "same" else -1
    out: list[Signal] = []
    last = -10 ** 9
    fired_day = None
    for i in range(1, len(idx) - 1):
        if hours[i] < int(signal_hour) or days[i] == fired_day or i - last < int(hold_bars):
            continue
        zi, a = known[i], atr[i]
        if not np.isfinite(zi) or abs(zi) < float(entry_z) or not np.isfinite(a) or a <= 0:
            continue
        side = int(np.sign(zi)) * int(exposure_sign) * flip
        if side == 0:
            continue
        px = close[i]
        out.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                          target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                          tag=f"china_stress_contagion:{direction}:w{int(window)}",
                          trigger=None, wait_bars=1))
        last = i
        fired_day = days[i]
    return out
