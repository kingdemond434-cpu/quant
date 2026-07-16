"""Crypto regime detection + per-regime performance."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.crypto_regime import regime_labels, regime_performance


def _panel(n: int = 400) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(2)
    idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
    cols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0.001, 0.03, (n, 3)), 0),
                         index=idx, columns=cols)
    funding = pd.DataFrame(rng.normal(0.0001, 0.0003, (n, 3)), index=idx, columns=cols)
    return close, funding


def test_regime_labels_cover_all_axes() -> None:
    close, funding = _panel()
    lab = regime_labels(close, funding)
    assert set(lab.columns) == {"trend", "vol", "funding"}
    assert set(lab["trend"].dropna().unique()) <= {"bull", "bear"}
    assert set(lab["vol"].dropna().unique()) <= {"high_vol", "low_vol"}


def test_regime_performance_buckets() -> None:
    close, funding = _panel()
    lab = regime_labels(close, funding)
    rng = np.random.default_rng(3)
    sleeves = {"a": rng.normal(0, 0.01, len(close)), "b": rng.normal(0, 0.01, len(close))}
    port = 0.5 * sleeves["a"] + 0.5 * sleeves["b"]
    perf = regime_performance(sleeves, lab, port)
    assert any(k.startswith("trend:") for k in perf)
    for v in perf.values():
        assert "portfolio" in v and "_days" in v
