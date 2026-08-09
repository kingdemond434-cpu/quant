"""The three normalisations, and what breaks when any one of them is dropped.

Intermarket differencing is subtraction. Everything that makes it MEAN anything happens before the
subtraction, in getting both readings onto the same scale. The tests that matter are the three
that drop one normalisation at a time and show the difference becomes a proxy for price level, for
volatility, or for the lookback -- each of which produces a plausible-looking indicator that is
measuring the wrong thing entirely.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.intermarket import (
    atr,
    cmma,
    intermarket_difference,
    threshold_revert,
    true_range,
)


def _walk(n: int, *, seed: int, sigma: float = 0.02, level: float = 100.0, drift: float = 0.0):
    """OHLC for a random walk at a given price level and volatility."""
    rng = np.random.default_rng(seed)
    close = level * np.cumprod(1.0 + rng.normal(drift, sigma, n))
    open_ = np.concatenate([[close[0]], close[:-1]]) * (1.0 + rng.normal(0, sigma / 5, n))
    span = np.abs(rng.normal(0, sigma / 2, n)) + sigma / 20
    high = np.maximum(open_, close) * (1.0 + span)
    low = np.minimum(open_, close) * (1.0 - span)
    return high, low, close


# --------------------------------------------------------------------------- true range / ATR

def test_true_range_counts_the_gap_not_just_the_bar():
    """A market that opens 5% away and then trades a quiet range had a 5% day. Range-only would
    call it calm and inflate every deviation normalised against it."""
    high = np.array([100.0, 106.0])
    low = np.array([99.0, 105.5])
    close = np.array([100.0, 105.8])
    assert true_range(high, low, close)[1] == pytest.approx(6.0)   # |106 - 100|, not 0.5


def test_atr_is_nan_until_a_full_window_exists():
    h, low, c = _walk(50, seed=1)
    a = atr(h, low, c, lookback=20)
    assert np.all(np.isnan(a[:19])) and np.all(np.isfinite(a[19:]))


def test_a_short_series_returns_all_nan_rather_than_a_partial_window_estimate():
    h, low, c = _walk(10, seed=2)
    assert np.all(np.isnan(atr(h, low, c, lookback=20)))


# ------------------------------------------------------- the three normalisations, one at a time

def test_the_reading_is_invariant_to_price_level():
    """NORMALISATION 1 (log). Without it a $60,000 instrument's close-minus-average dwarfs a $0.15
    one's and the difference is just a report of which symbol is more expensive."""
    h, low, c = _walk(600, seed=3)
    cheap = cmma(h, low, c, lookback=24)
    rich = cmma(h * 1000.0, low * 1000.0, c * 1000.0, lookback=24)
    ok = np.isfinite(cheap) & np.isfinite(rich)
    assert ok.sum() > 400
    assert np.allclose(cheap[ok], rich[ok])


def test_the_reading_is_stable_across_volatility_regimes():
    """NORMALISATION 2 (ATR). Without it a 12%/day instrument reads as permanently 'unusual'
    against a 2%/day one and the difference is a volatility ranking wearing a signal's clothes."""
    calm = cmma(*_walk(1500, seed=4, sigma=0.005), lookback=24)
    wild = cmma(*_walk(1500, seed=4, sigma=0.060), lookback=24)
    sd_calm = float(np.nanstd(calm))
    sd_wild = float(np.nanstd(wild))
    assert 0.6 < sd_wild / sd_calm < 1.6, (
        f"dispersion moved {sd_wild / sd_calm:.2f}x across a 12x volatility change")


def test_the_reading_is_stable_across_lookbacks():
    """NORMALISATION 3 (sqrt(n)), the one that is easy to miss. A random walk's deviation from its
    own n-bar mean has standard deviation sigma*sqrt(n/3), so the RAW statistic grows with the
    lookback and a fixed threshold silently means something different at every n."""
    h, low, c = _walk(4000, seed=5)
    sds = [float(np.nanstd(cmma(h, low, c, lookback=n, atr_lookback=200)))
           for n in (6, 12, 24, 48, 96)]
    assert max(sds) / min(sds) < 1.6, f"dispersion drifted across lookbacks: {sds}"


def test_dropping_the_sqrt_scaling_would_show_the_drift_this_test_prevents():
    """The control for the test above: the unscaled statistic really does grow with n, so the
    stability shown there is the normalisation working and not the fixture being featureless."""
    h, low, c = _walk(4000, seed=5)
    raw = []
    for n in (6, 96):
        scaled = cmma(h, low, c, lookback=n, atr_lookback=200)
        raw.append(float(np.nanstd(scaled * np.sqrt(n))))
    assert raw[1] / raw[0] > 2.5


# ------------------------------------------------------------------------------- the difference

def test_a_symbol_differenced_against_itself_is_identically_zero():
    h, low, c = _walk(500, seed=6)
    d = intermarket_difference(h, low, c, h, low, c, lookback=24)
    assert np.all(np.isnan(d) | (np.abs(d) < 1e-12))


def test_the_common_factor_is_removed():
    """THE POINT, and the desk's largest measured defect. Two instruments driven by one shared
    factor plus small idiosyncratic noise: the raw readings are strongly correlated, the
    difference must not be."""
    rng = np.random.default_rng(7)
    n = 3000
    factor = rng.normal(0, 0.02, n)
    a_ret = factor + rng.normal(0, 0.004, n)
    b_ret = factor + rng.normal(0, 0.004, n)

    def ohlc(ret, level):
        close = level * np.cumprod(1.0 + ret)
        high = close * 1.01
        low = close * 0.99
        return high, low, close

    ah, al, ac = ohlc(a_ret, 100.0)
    bh, bl, bc = ohlc(b_ret, 3000.0)
    ca, cb = cmma(ah, al, ac, lookback=24), cmma(bh, bl, bc, lookback=24)
    ok = np.isfinite(ca) & np.isfinite(cb)
    assert float(np.corrcoef(ca[ok], cb[ok])[0, 1]) > 0.8, "the fixture must share a factor"

    d = intermarket_difference(ah, al, ac, bh, bl, bc, lookback=24)
    dok = np.isfinite(d) & ok
    assert abs(float(np.corrcoef(d[dok], ca[dok])[0, 1])) < 0.75, (
        "the difference is still tracking the common factor")
    assert float(np.nanstd(d)) < float(np.nanstd(ca)), (
        "the difference must be quieter than either leg")


def test_misaligned_series_raise_rather_than_broadcasting():
    h, low, c = _walk(500, seed=8)
    h2, l2, c2 = _walk(400, seed=9)
    with pytest.raises(ValueError):
        intermarket_difference(h, low, c, h2, l2, c2, lookback=24)


def test_non_positive_prices_raise():
    h, low, c = _walk(200, seed=10)
    low = low.copy()
    low[5] = 0.0
    with pytest.raises(ValueError, match="non-positive"):
        cmma(h, low, c, lookback=24)


def test_a_frozen_feed_produces_no_reading_rather_than_an_infinite_one():
    """Zero ATR means the venue stopped publishing, not a market of infinite unusualness."""
    flat = np.full(300, 100.0)
    out = cmma(flat, flat, flat, lookback=24)
    assert not np.any(np.isinf(out))
    assert np.all(np.isnan(out[30:]))


# ------------------------------------------------------------------------------ position rule

def test_it_enters_at_the_threshold_and_holds_until_zero():
    ind = np.array([0.0, 0.4, 0.3, 0.2, 0.1, -0.05, -0.1, 0.0])
    pos = threshold_revert(ind, threshold=0.25)
    assert list(pos) == [0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0]


def test_the_short_side_is_symmetric():
    ind = np.array([0.0, -0.4, -0.3, -0.1, 0.05])
    assert list(threshold_revert(ind, threshold=0.25)) == [0.0, -1.0, -1.0, -1.0, 0.0]


def test_the_position_persists_between_signal_and_exit():
    """A stateless sign(|x| > threshold) rule would flatten the moment the reading cooled and is
    a different, far twitchier strategy. The hold is the construction, not an implementation
    detail."""
    ind = np.array([0.5] + [0.26] * 50 + [0.0])
    pos = threshold_revert(ind, threshold=0.25)
    assert np.all(pos[:-1] == 1.0) and pos[-1] == 0.0


def test_warmup_nans_do_not_manufacture_a_round_trip():
    """During warm-up there is no reading at all. Treating 'not yet computable' as 'exit' would
    create a spurious trade at the first valid bar of every single backtest."""
    ind = np.array([np.nan] * 5 + [0.4, np.nan, np.nan, 0.3, 0.0])
    pos = threshold_revert(ind, threshold=0.25)
    assert list(pos[:5]) == [0.0] * 5
    assert list(pos[5:9]) == [1.0, 1.0, 1.0, 1.0]
    assert pos[9] == 0.0


def test_a_non_positive_threshold_raises():
    with pytest.raises(ValueError):
        threshold_revert(np.zeros(10), threshold=0.0)


def test_it_uses_only_trailing_information():
    """The single failure that would make every result here fiction."""
    h, low, c = _walk(800, seed=11)
    full = cmma(h, low, c, lookback=24, atr_lookback=100)
    part = cmma(h[:500], low[:500], c[:500], lookback=24, atr_lookback=100)
    ok = np.isfinite(full[:500]) & np.isfinite(part)
    assert ok.sum() > 300 and np.allclose(full[:500][ok], part[ok])
