"""The numpy bar binning in `intrabar_path` / `realized_variation` is the groupby, faster.

2026-11-05: MT5-TapeFeatures was killed at its 45-minute limit 12 runs in a row, and 54% of
`build_day` on a 192k-tick day was per-bar pandas `.loc` inside `intrabar_path`. The segments
must reproduce the groupby EXACTLY -- same bars, same labels and resolution, same first/last/
argmax order on unsorted and gapped tapes -- or every intrabar artifact silently changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import microstructure as ms  # noqa: E402

FREQS = ("1min", "5min", "15min", "1h", "4h", "1D")
POINT = 1e-5


def _quotes(seed: int, n_per_hour: int, *, shuffle: bool, drop_hour: int | None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    d0 = int(np.datetime64("2026-10-01T00:00", "ms").astype("int64"))
    t = np.concatenate([d0 + h * 3_600_000 + np.sort(rng.integers(0, 3_600_000, n_per_hour))
                        for h in range(24) if h != drop_hour])
    bid = 1.1 + np.cumsum(rng.choice([-1, 0, 1], size=t.size)) * POINT
    df = pd.DataFrame({"time_msc": t, "bid": bid, "ask": bid + 12 * POINT})
    if shuffle:
        df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return ms.quote_frame(df, POINT)


def _groupby_path(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    orig = ms._intrabar_path_fast
    ms._intrabar_path_fast = lambda d, f: None      # the original groupby path
    try:
        return ms.intrabar_path(df, freq)
    finally:
        ms._intrabar_path_fast = orig


@pytest.mark.parametrize("shuffle,drop_hour", [(False, None), (True, None), (False, 5)])
@pytest.mark.parametrize("freq", FREQS)
def test_the_fast_path_is_the_groupby_exactly(freq, shuffle, drop_hour) -> None:
    df = _quotes(7, 600, shuffle=shuffle, drop_hour=drop_hour)
    pd.testing.assert_frame_equal(ms.intrabar_path(df, freq), _groupby_path(df, freq),
                                  check_freq=False)


@pytest.mark.parametrize("freq", FREQS)
def test_the_variation_bars_are_the_groupby_bars(freq) -> None:
    df = _quotes(3, 900, shuffle=False, drop_hour=11)
    ts = pd.to_datetime(np.asarray(df["time_msc"], dtype=np.int64), unit="ms", utc=True)
    grid = (pd.Series(np.asarray(df["mid"], dtype=np.float64), index=ts).sort_index()
            .resample(f"{int(ms.RV_SAMPLE_MS)}ms").last().ffill().dropna())
    order, starts, labels = ms._bar_segments(pd.DatetimeIndex(grid.index), freq)
    ends = np.r_[starts[1:], grid.size]
    fast = [(labels[a], order[a:b].tolist()) for a, b in zip(starts, ends, strict=True)]
    slow = [(stamp, idx.to_numpy().tolist()) for stamp, idx in
            pd.Series(np.arange(grid.size), index=grid.index).groupby(pd.Grouper(freq=freq))
            if idx.size]
    assert fast == slow


def test_a_nan_mid_takes_the_original_path() -> None:
    df = _quotes(1, 50, shuffle=False, drop_hour=None)
    df.loc[df.index[3], "mid"] = np.nan
    assert ms._intrabar_path_fast(df, "1h") is None
