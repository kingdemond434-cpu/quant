"""Live<->backtest parity guard (lesson from nautechsystems/nautilus_trader).

``crypto_sleeves._book`` (the backtest) and ``crypto_sleeves.latest_weights`` (what the live
executor targets now) are two HAND-MAINTAINED code paths for the same cross-sectional book.
Nautilus's core guarantee is that sim and live share one path; we cannot get that without a refactor
of live alpha code, so this pins the invariants parity REQUIRES and documents the one known gap.

KNOWN DIVERGENCE (reported, deliberately not asserted as correct): ``_book`` sizes with inverse-vol
LAGGED one bar (crypto_sleeves.py, ``ret.rolling(vol_window).std().shift(1)``), while
``latest_weights`` uses vol through the final bar (no shift). Leg MEMBERSHIP and dollar-neutrality
still match (both lag the *signal*); only the inverse-vol MAGNITUDES differ. This guards membership
+ neutrality; reconciling the magnitude convention is a follow-up for the operator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research.crypto_sleeves import latest_weights


def _panels(
    n_bars: int = 60, n_names: int = 15, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    cols = [f"S{i}" for i in range(n_names)]
    idx = pd.date_range("2026-01-01", periods=n_bars, freq="D", tz="UTC")
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, (n_bars, n_names)), axis=0))
    close = pd.DataFrame(prices, index=idx, columns=cols)
    signal = pd.DataFrame(rng.normal(0.0, 1.0, (n_bars, n_names)), index=idx, columns=cols)
    return close, signal


def test_latest_weights_is_dollar_neutral_and_bounded() -> None:
    close, signal = _panels()
    w = latest_weights(close, signal, q=0.2, vol_window=30, min_names=5, long_low=True)
    longs = [v for v in w.values() if v > 0]
    shorts = [v for v in w.values() if v < 0]
    assert sum(longs) == pytest.approx(0.5, abs=1e-9)
    assert sum(shorts) == pytest.approx(-0.5, abs=1e-9)
    assert all(-0.5 <= v <= 0.5 for v in w.values())


def test_leg_membership_matches_the_backtest_ranking() -> None:
    close, signal = _panels(seed=1)
    q, min_names, long_low = 0.2, 5, True
    w = latest_weights(close, signal, q=q, vol_window=30, min_names=min_names, long_low=long_low)
    # Independent reproduction of the ranking _book uses (lagged signal, same q / long_low):
    s = signal.shift(1).iloc[-1].dropna()
    s = s[close.iloc[-1].reindex(s.index).notna()].dropna()
    k = max(1, int(len(s) * q))
    ranked = s.sort_values(ascending=long_low)
    expected_longs, expected_shorts = set(ranked.index[:k]), set(ranked.index[-k:])
    got_longs = {name for name, v in w.items() if v > 0}
    got_shorts = {name for name, v in w.items() if v < 0}
    assert got_longs == expected_longs
    assert got_shorts == expected_shorts
