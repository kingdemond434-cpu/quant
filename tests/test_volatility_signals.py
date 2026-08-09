"""Direction-agnostic signal properties.

Two of these caught real bugs while being written, and both bugs were the kind that ship:

  test_a_frozen_series_produces_no_position_rather_than_a_fictional_one -- numpy returns ~5e-38
  rather than 0.0 for the variance of a constant series, so the original `rv > 0` guard passed and
  the premium came out at 1.4e31, firing on every bar of any pegged, halted or frozen series.
  test_garman_klass_is_non_negative_on_every_valid_bar -- the module originally documented the
  estimator as able to go negative in normal markets. It cannot: the algebra bounds it at
  0.1137 * ln(H/L)^2. That mistake would have thrown away the far more useful reading, which is
  that a negative value is a PROOF of corrupt data.

test_forecast_never_sees_its_own_bar is the standing one: it is the difference between a forecast
and a description, and getting it wrong produces a spectacular backtest that is simply reading
the answer.
"""
from __future__ import annotations

import numpy as np

from libs.research.volatility_signals import (
    ewma_variance,
    garman_klass,
    invalid_bars,
    prediction_premium,
    premium_signal,
    realised_variance,
)


def _ohlc(n: int = 500, seed: int = 0):
    rng = np.random.default_rng(seed)
    close = np.cumprod(1.0 + rng.normal(0.0005, 0.02, n)) * 100.0
    open_ = np.concatenate([[close[0]], close[:-1]])
    span = np.abs(rng.normal(0.0, 0.01, n)) + 0.002
    high = np.maximum(open_, close) * (1.0 + span)
    low = np.minimum(open_, close) * (1.0 - span)
    return high, low, close, open_


# ------------------------------------------------------------------------ Garman-Klass

def test_garman_klass_rises_with_true_volatility():
    quiet = _ohlc(seed=1)
    loud = tuple(x for x in _ohlc(seed=2))
    h, lo, c, o = loud
    h, lo = h * 1.05, lo * 0.95          # widen the range only
    assert np.nanmean(garman_klass(h, lo, c, o)) > np.nanmean(garman_klass(*quiet))


def test_garman_klass_is_zero_on_a_bar_that_never_moved():
    flat = np.array([100.0, 100.0])
    assert np.allclose(garman_klass(flat, flat, flat, flat), 0.0)


def test_garman_klass_is_non_negative_on_every_valid_bar():
    """Provable, not empirical: open and close lie inside [low, high], so |ln(C/O)| <= ln(H/L)
    and GK >= 0.1137 * ln(H/L)^2. The extreme case -- opened at the low, closed at the high --
    is the tightest and is still positive."""
    assert garman_klass(np.array([110.0]), np.array([100.0]),
                        np.array([110.0]), np.array([100.0]))[0] > 0.0
    rng = np.random.default_rng(20)
    for seed in range(8):
        h, lo, c, o = _ohlc(300, seed=seed + rng.integers(100))
        gk = garman_klass(h, lo, c, o)
        assert np.all(gk[np.isfinite(gk)] >= -1e-15)


def test_a_negative_garman_klass_flags_a_corrupt_bar():
    """The more valuable half of the function. A close outside its own bar's range cannot happen
    in a market and always means a broken join, merge or backfill -- so this is a free integrity
    check on every bar the desk stores, and it must NOT be clipped into silence."""
    h, lo = np.array([101.0, 101.0]), np.array([100.0, 100.0])
    o = np.array([100.5, 100.5])
    c = np.array([100.5, 130.0])          # second bar closes far above its own high
    gk = garman_klass(h, lo, c, o)
    assert gk[0] >= 0.0 and gk[1] < 0.0
    assert list(invalid_bars(h, lo, c, o)) == [False, True]


def test_garman_klass_survives_degenerate_prices_without_raising():
    z = np.zeros(4)
    out = garman_klass(z, z, z, z)
    assert len(out) == 4 and not np.isfinite(out).all()


# ------------------------------------------------------------------------------- EWMA

def test_forecast_never_sees_its_own_bar():
    """out[i] must be built only from returns strictly before i. Prefix invariance proves it:
    truncating the series cannot change an earlier forecast."""
    rng = np.random.default_rng(3)
    r = rng.normal(0.0, 0.02, 600)
    full = ewma_variance(r)
    part = ewma_variance(r[:400])
    assert np.allclose(full[:400], part, equal_nan=True)


def test_a_variance_spike_moves_the_next_forecast_not_the_current_one():
    r = np.full(200, 0.001)
    r[150] = 0.30
    v = ewma_variance(r)
    assert v[151] > v[150], "the shock must land on the FOLLOWING forecast"


def test_ewma_tracks_a_known_variance():
    rng = np.random.default_rng(4)
    r = rng.normal(0.0, 0.05, 4000)
    assert abs(float(np.nanmean(ewma_variance(r))) - 0.05 ** 2) < 0.0006


def test_realised_variance_uses_only_trailing_bars():
    rng = np.random.default_rng(5)
    r = rng.normal(0.0, 0.02, 500)
    assert np.allclose(realised_variance(r)[:300], realised_variance(r[:300])[:300],
                       equal_nan=True)


# -------------------------------------------------------------------------- the premium

def test_premium_is_scale_free_across_assets():
    """Scaled by realised variance so a cross-sectional use ranks premia, not volatilities. If it
    were a raw difference the loudest asset would dominate every ranking."""
    rng = np.random.default_rng(6)
    r = rng.normal(0.0, 0.01, 900)
    a = prediction_premium(r)
    b = prediction_premium(r * 10.0)          # same process, ten times the volatility
    ok = np.isfinite(a) & np.isfinite(b)
    assert np.allclose(a[ok], b[ok], atol=1e-9)


def test_premium_is_positive_when_forecast_exceeds_realised():
    """A burst of large moves followed by calm: the forecast still carries the shock while
    realised variance has moved on, so the premium must be positive."""
    r = np.concatenate([np.full(200, 0.001), np.full(5, 0.25), np.full(40, 0.001)])
    prem = prediction_premium(r, n=21)
    assert np.nanmax(prem[206:230]) > 0.0


def test_signal_is_bounded_and_sparse():
    rng = np.random.default_rng(7)
    r = rng.normal(0.0, 0.02, 2000)
    s = premium_signal(r)
    assert set(np.unique(s)).issubset({-1.0, 0.0, 1.0})
    assert float(np.mean(s != 0.0)) < 0.35, "a 1.5-sigma threshold must not fire most of the time"


def test_signal_uses_only_trailing_history():
    rng = np.random.default_rng(8)
    r = rng.normal(0.0, 0.02, 1400)
    assert np.array_equal(premium_signal(r)[:900], premium_signal(r[:900])[:900])


def test_signal_is_flat_before_it_has_a_threshold_to_judge_against():
    rng = np.random.default_rng(9)
    r = rng.normal(0.0, 0.02, 400)
    assert np.all(premium_signal(r, window=126)[:126] == 0.0)


def test_a_frozen_series_produces_no_position_rather_than_a_fictional_one():
    """The bug this test was written to catch and did. numpy returns ~5e-38 rather than exactly
    0.0 for the variance of a constant series, so a `rv > 0` guard passes and dividing forecast
    dust by realised dust gave a premium of 1.4e31 that fired on every bar. The series where this
    happens are real and common -- a pegged pair, a halted market, a dead altcoin, a frozen feed
    -- and they are precisely the ones whose enormous fake Sharpe nobody questions."""
    for frozen in (np.full(600, 0.001), np.zeros(600)):
        s = premium_signal(frozen)
        assert np.all(np.isfinite(s))
        assert np.all(s == 0.0), "a series with no variance cannot carry a variance premium"
    prem = prediction_premium(np.full(600, 0.001))
    assert not np.isfinite(prem).any(), "premium must be undefined, never astronomically large"
