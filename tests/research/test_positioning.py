"""Positioning mechanisms, and the units conversion that makes implied variance comparable.

libs/research/positioning.py exists because slot_registry has listed `oi_divergence` and
`ls_contrarian` as forward-slot candidates for weeks with NO function anywhere computing them --
a required input with no producer, which is lesson L0040 in its purest form. These tests lock the
mechanism claims so the implementations cannot drift into something the docstrings do not say.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.positioning import (
    LS_EXTREME_PCT,
    ls_contrarian,
    oi_divergence,
    oi_price_state,
)
from libs.research.volatility_signals import dvol_to_variance, prediction_premium

# ------------------------------------------------------------------- OI / price state

def test_the_four_states_are_labelled_by_their_sign_pair():
    n = 5
    up = np.arange(20, dtype="float64") + 100.0
    down = 120.0 - np.arange(20, dtype="float64")
    oi_up = np.arange(20, dtype="float64") + 1000.0
    oi_dn = 1020.0 - np.arange(20, dtype="float64")
    assert oi_price_state(up, oi_up, n=n)[-1] == 0        # price up,   OI up
    assert oi_price_state(up, oi_dn, n=n)[-1] == 1        # price up,   OI down
    assert oi_price_state(down, oi_up, n=n)[-1] == 2      # price down, OI up
    assert oi_price_state(down, oi_dn, n=n)[-1] == 3      # price down, OI down


def test_a_flat_series_is_unlabelled_rather_than_falling_through_to_a_branch():
    """Neither 'up' nor 'down' is true when nothing moved. Assigning such a bar to whichever
    comparison happens to be False would put real weight on non-events."""
    flat = np.full(20, 100.0)
    oi = np.arange(20, dtype="float64") + 1000.0
    assert np.all(oi_price_state(flat, oi, n=5)[5:] == -1)


def test_bars_without_enough_history_are_unlabelled():
    c = np.arange(10, dtype="float64") + 100.0
    assert np.all(oi_price_state(c, c * 10.0, n=5)[:5] == -1)


def test_mismatched_input_lengths_raise_rather_than_silently_align():
    with pytest.raises(ValueError):
        oi_price_state(np.zeros(10), np.zeros(9))


def test_a_zero_open_interest_feed_does_not_produce_an_infinite_signal():
    c = np.arange(40, dtype="float64") + 100.0
    assert np.all(np.isfinite(oi_divergence(c, np.zeros(40))))


# ---------------------------------------------------------------------- OI divergence

def test_it_fades_only_the_unconfirmed_moves():
    """The mechanism describes two cells of four. Trading the confirmed cells too would make it a
    generic reversal signal and the OI would be decoration."""
    n = 5
    up, oi_dn = np.arange(20, dtype="float64") + 100.0, 1020.0 - np.arange(20, dtype="float64")
    up2, oi_up = up.copy(), np.arange(20, dtype="float64") + 1000.0
    assert oi_divergence(up, oi_dn, n=n)[-1] == -1.0   # rally on falling OI -> short
    assert oi_divergence(up2, oi_up, n=n)[-1] == 0.0   # rally on rising OI  -> flat


def test_the_sign_says_fade_not_follow():
    """An inverted sign would test the opposite hypothesis while producing identical-looking
    results. Price DOWN on falling OI is longs capitulating -- forced selling -- so the position
    is LONG."""
    down = 120.0 - np.arange(20, dtype="float64")
    oi_dn = 1020.0 - np.arange(20, dtype="float64")
    assert oi_divergence(down, oi_dn, n=5)[-1] == 1.0


def test_the_signal_is_bounded_and_sparse():
    rng = np.random.default_rng(3)
    c = np.cumprod(1 + rng.normal(0, 0.02, 900)) * 100
    oi = np.cumprod(1 + rng.normal(0, 0.01, 900)) * 1e6
    p = oi_divergence(c, oi)
    assert set(np.unique(p)).issubset({-1.0, 0.0, 1.0})
    assert float(np.mean(p != 0)) < 0.7


def test_it_uses_only_trailing_history():
    rng = np.random.default_rng(4)
    c = np.cumprod(1 + rng.normal(0, 0.02, 600)) * 100
    oi = np.cumprod(1 + rng.normal(0, 0.01, 600)) * 1e6
    assert np.array_equal(oi_divergence(c, oi)[:400], oi_divergence(c[:400], oi[:400]))


# ------------------------------------------------------------------ long/short contrarian

def test_it_fades_the_crowd_at_a_trailing_extreme():
    r = np.concatenate([np.full(120, 1.0) + np.random.default_rng(5).normal(0, 0.05, 120),
                        [5.0]])          # a sharp crowd-long reading
    assert ls_contrarian(r, window=90)[-1] == -1.0
    r2 = np.concatenate([r[:-1], [0.05]])
    assert ls_contrarian(r2, window=90)[-1] == 1.0


def test_thresholds_are_trailing_percentiles_not_fixed_levels():
    """A ratio of 3.0 means something different on BTC than on an altcoin, and different in a bull
    market than a bear one. Ranking against the FULL sample would also leak the future into every
    early bar -- the most common way a positioning study flatters itself."""
    rng = np.random.default_rng(6)
    r = np.abs(rng.normal(1.0, 0.3, 800)) + 0.1
    assert np.array_equal(ls_contrarian(r)[:500], ls_contrarian(r[:500])[:500])


def test_a_frozen_feed_is_not_read_as_a_consensus():
    """Every reading identical means the venue stopped publishing, not that the crowd agrees. The
    percentile spread collapses and must produce no position rather than a maximal one."""
    assert np.all(ls_contrarian(np.full(400, 1.0)) == 0.0)


def test_it_is_flat_before_it_has_a_trailing_window():
    rng = np.random.default_rng(7)
    assert np.all(ls_contrarian(np.abs(rng.normal(1.0, 0.3, 300)), window=90)[:90] == 0.0)


def test_the_extreme_percentile_is_wide_enough_to_be_testable():
    """A 5% tail on daily data fires a handful of times a year and can never reach validate()'s
    250-observation floor on any history this desk owns."""
    assert 10.0 <= LS_EXTREME_PCT <= 25.0


# ------------------------------------------------------------- implied variance units

def test_dvol_converts_percent_annual_vol_to_per_period_variance():
    """Three conversions, and skipping any one is an orders-of-magnitude error: percent ->
    fraction, vol -> variance, annual -> per-period."""
    got = dvol_to_variance(np.array([50.0]), periods_per_year=365.0)[0]
    assert got == pytest.approx(0.25 / 365.0)


def test_raw_dvol_would_inflate_the_premium_by_about_a_year_of_periods():
    """The units error this function exists to prevent. Passing DVOL raw is wrong by roughly
    periods_per_year, which produces a spectacular and entirely fictional premium."""
    raw, converted = 50.0, dvol_to_variance(np.array([50.0]), periods_per_year=365.0)[0]
    assert raw / converted > 1e4


def test_supplying_implied_variance_replaces_the_ewma_forecast():
    rng = np.random.default_rng(8)
    r = rng.normal(0.0, 0.02, 600)
    base = prediction_premium(r)
    iv = prediction_premium(r, implied_variance=np.full(600, 0.02 ** 2 * 3.0))
    ok = np.isfinite(base) & np.isfinite(iv)
    assert not np.allclose(base[ok], iv[ok]), "the supplied forecast must actually be used"
    assert np.nanmedian(iv[ok]) > np.nanmedian(base[ok]), "3x variance priced -> positive premium"


def test_misaligned_implied_variance_raises_rather_than_broadcasting():
    with pytest.raises(ValueError):
        prediction_premium(np.zeros(600), implied_variance=np.zeros(599))
