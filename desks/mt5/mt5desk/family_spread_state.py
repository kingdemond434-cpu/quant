"""Trade the instrument's OWN spread state -- the one column in the bars nobody mines for alpha.

WHAT IS PROPRIETARY HERE. Every H1 bar this desk holds carries the broker's `spread` at that
bar and its `tick_volume`. Both are Fusion's numbers on Fusion's clock: no public dataset has
them, and every cost model on this desk reads the spread only to charge it. Yet a spread is
information -- it is the venue telling you how much it wants to be paid to take the other side
right now -- and the desk had no family that could condition on it.

THREE CLAIMS, each an economic statement about what a spread state means:

    spike_reversion   the spread jumps far above its own trailing norm on a bar that also moved;
                      the move was liquidity, not information, and fades as the spread normalises
    calm_continuation the spread is unusually tight AND activity unusually high -- a deep,
                      competitive book -- and a move made in that state carries
    widening_avoid    not a trade: the family returns nothing when the spread is in its own top
                      percentile, and `plumbing_miner`'s screen refuses fills there anyway.
                      Listed because a family that trades INTO a widening spread is the cell the
                      cost model would never have priced right

EVERY THRESHOLD IS THE INSTRUMENT'S OWN. Percentiles of its trailing spread and activity, over
`norm_window` bars, so a structurally wide exotic is judged against itself and a tight major
against itself. A fixed points threshold would compare gold to EURUSD, which is not a claim.

REFUSES without a `spread` column: a spread family on bars that carry no spread is a price
family wearing a better name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1

MODES = ("spike_reversion", "calm_continuation")


def family_spread_state(
    df: pd.DataFrame,
    *,
    mode: str = "spike_reversion",
    norm_window: int = 240,
    spike_pct: float = 0.95,
    calm_pct: float = 0.20,
    active_pct: float = 0.80,
    min_move_atr: float = 0.5,
    hold_bars: int = 6,
    atr_n: int = 20,
    stop_atr: float = 2.0,
    rr: float = 1.5,
) -> list[Signal]:
    if mode not in MODES or "spread" not in df.columns:
        return []
    d = _h1(df)
    if len(d) < norm_window * 3:
        return []
    # `_h1` RESAMPLES TO OHLC AND DROPS EVERY OTHER COLUMN. The first version read the spread
    # from `d` and returned no signals on every instrument, in 0.0 seconds, with no error -- the
    # exact shape of a family that is dead while looking registered. The broker's columns are
    # taken from the ORIGINAL frame and aligned to the resampled index.
    raw = df.copy()
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.index, utc=True, errors="coerce"))
    spread = raw["spread"].astype(float).reindex(d.index).ffill()
    if not np.isfinite(spread.to_numpy()).any() or float(spread.std()) <= 0:
        return []
    close = d["close"].astype(float)
    ret = close.diff()
    atr = _atr(d, atr_n)

    def _rank(series: pd.Series) -> pd.Series:
        """Trailing percentile of the current value within its own window, strictly causal.

        Vectorised: for each bar, the fraction of the previous `norm_window` values at or below
        it. A rolling-apply over 35,000 bars was the slow path; this is the same number.
        """
        v = series.to_numpy(dtype=float)
        n = v.size
        out = np.full(n, np.nan)
        if n <= norm_window:
            return pd.Series(out, index=series.index)
        from numpy.lib.stride_tricks import sliding_window_view
        win = sliding_window_view(v, norm_window + 1)              # (n-norm, norm+1)
        prev, cur = win[:, :-1], win[:, -1:]
        out[norm_window:] = (prev <= cur).mean(axis=1)
        return pd.Series(out, index=series.index)

    sp_rank = _rank(spread)
    has_vol = "tick_volume" in raw.columns
    act_rank = (_rank(raw["tick_volume"].astype(float).reindex(d.index).ffill())
                if has_vol else pd.Series(np.nan, index=d.index))

    signals: list[Signal] = []
    last = -10 ** 9
    idx = d.index
    for i in range(norm_window, len(idx) - 1):
        if i - last < hold_bars:
            continue
        a = float(atr.iloc[i])
        if not np.isfinite(a) or a <= 0:
            continue
        mv = float(ret.iloc[i])
        if not np.isfinite(mv) or abs(mv) < min_move_atr * a:
            continue
        sr = float(sp_rank.iloc[i])
        if not np.isfinite(sr):
            continue
        if mode == "spike_reversion":
            if sr < spike_pct:
                continue
            side = -1 if mv > 0 else 1
        else:
            ar = float(act_rank.iloc[i]) if has_vol else np.nan
            if sr > calm_pct or (has_vol and (not np.isfinite(ar) or ar < active_pct)):
                continue
            side = 1 if mv > 0 else -1
        px = float(close.iloc[i])
        signals.append(Signal(time=idx[i], side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=int(hold_bars),
                              tag=f"spread_state:{mode}", trigger=None, wait_bars=1))
        last = i
    return signals
