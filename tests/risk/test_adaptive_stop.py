"""The adaptive-stop risk layer: an unmeasured signature is None (never a default multiplier),
the five disclosed factors move the multiplier in the stated directions, and the clamp holds."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.risk import adaptive_stop as A


def _bars(n: int, *, seed: int = 7, wick: float = 0.5, trend: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(trend, 1.0, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    hi = np.maximum(open_, close) + wick * rng.random(n)
    lo = np.minimum(open_, close) - wick * rng.random(n)
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close})


def _sig(**over: float) -> A.Signature:
    base = {"mean_true_range": 1.0, "mean_range": 1.0, "mean_body": 0.5,
            "mean_pullback": 1.0, "tr_cv": 0.5, "run_length": 1.7, "n_bars": 1000}
    base.update(over)
    return A.Signature(**base)  # type: ignore[arg-type]


def test_fewer_than_500_bars_or_none_is_unmeasured() -> None:
    assert A.signature(None) is None  # type: ignore[arg-type]
    assert A.signature(_bars(499)) is None
    assert A.stop_distance(None, 1.0) is None


def test_signature_reads_only_the_lookback_window() -> None:
    df = _bars(1500)
    sig = A.signature(df, lookback=1000)
    assert sig is not None and sig.n_bars == 1000
    # identical to computing on the tail alone: the earlier 500 bars never enter it
    tail = A.signature(df.iloc[-1000:].reset_index(drop=True), lookback=1000)
    assert tail == sig
    assert sig.mean_true_range >= sig.mean_range - 1e-12      # TR includes gaps
    assert 0.0 < sig.noise_ratio <= 1.0
    assert sig.run_length >= 1.0 and sig.tr_cv > 0


def test_flat_bars_have_no_true_range_and_are_unmeasured() -> None:
    flat = pd.DataFrame({c: np.full(600, 50.0) for c in ("open", "high", "low", "close")})
    assert A.signature(flat) is None


def test_noise_ratio_defaults_to_one_on_a_zero_range() -> None:
    assert _sig(mean_range=0.0).noise_ratio == 1.0
    assert _sig(mean_body=0.25, mean_range=1.0).noise_ratio == 0.25


def test_wicky_symbols_get_wider_stops_than_clean_ones() -> None:
    clean = A.adaptive_multiplier(_sig(mean_body=0.9))
    wicky = A.adaptive_multiplier(_sig(mean_body=0.1))
    assert wicky > clean


def test_trend_persistence_tiers_are_the_sources_boundaries() -> None:
    persistent = A.adaptive_multiplier(_sig(run_length=2.0))
    middle = A.adaptive_multiplier(_sig(run_length=1.5))
    choppy = A.adaptive_multiplier(_sig(run_length=1.49))
    assert persistent < middle < choppy
    assert middle / persistent == pytest.approx(1.00 / 0.85)
    assert choppy / middle == pytest.approx(1.20)


def test_spread_and_volvol_widen_and_are_capped() -> None:
    m0 = A.adaptive_multiplier(_sig(), spread=0.0)
    m_wide = A.adaptive_multiplier(_sig(), spread=0.1)
    m_huge = A.adaptive_multiplier(_sig(), spread=10.0)
    assert m0 < m_wide < m_huge
    assert m_huge / m0 == pytest.approx(1.30)                 # spread factor clamps at 1.30
    assert A.adaptive_multiplier(_sig(tr_cv=5.0)) / A.adaptive_multiplier(_sig(tr_cv=0.0)) \
        == pytest.approx(1.40 / 0.90)


def test_multiplier_is_clamped_to_its_band() -> None:
    extreme = _sig(mean_body=0.0, mean_pullback=10.0, tr_cv=10.0, run_length=1.0)
    assert A.adaptive_multiplier(extreme, spread=10.0) == 4.0
    calm = _sig(mean_body=1.0, mean_pullback=0.0, tr_cv=0.0, run_length=3.0)
    assert A.adaptive_multiplier(calm, base=0.1) == 1.0
    assert A.adaptive_multiplier(extreme, hi=2.5, spread=10.0) == 2.5


def test_stop_distance_scales_current_atr_and_refuses_a_bad_atr() -> None:
    sig = _sig()
    m = A.adaptive_multiplier(sig, 0.05)
    assert A.stop_distance(sig, 2.0, 0.05) == pytest.approx(2.0 * m)
    assert A.stop_distance(sig, 0.0) is None
    assert A.stop_distance(sig, float("nan")) is None
