from __future__ import annotations

import numpy as np
import pandas as pd

from mt5desk.family_style_premia import _bars_per_day, _score


def _h1(days: int = 300) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=days * 24, freq="h", tz="UTC")
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0,
                         "close": np.exp(np.linspace(np.log(100), np.log(130), len(idx)))},
                        index=idx)


def test_style_horizons_are_days_not_h1_bars() -> None:
    d = _h1()
    assert _bars_per_day(d) == 24
    momentum = _score(d, "momentum", swap_diff=None, risk=None, speeds=(21, 63, 252))
    assert momentum is not None
    assert momentum.iloc[: 252 * 24].isna().all()
    assert momentum.iloc[252 * 24 :].notna().any()


def test_defensive_is_index_only() -> None:
    d = _h1()
    assert _score(d, "defensive", swap_diff=None, risk=d, speeds=(21, 63, 252),
                  asset_class="Forex") is None
    assert _score(d, "defensive", swap_diff=None, risk=d, speeds=(21, 63, 252),
                  asset_class="Indices") is not None
