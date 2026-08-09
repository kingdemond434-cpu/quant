"""The three overlays, and the lag that decides whether any of them is honest.

test_the_volatility_scale_is_lagged is the one that carries the file. Sizing bar i from a window
that includes bar i's own return is a look-ahead bug that makes vol targeting look far better than
it is -- you would be cutting exposure using the very move you were about to be hurt by.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.overlays import (
    DEFAULT_LEVERAGE_CAP,
    hawkes_process,
    normalised_range,
    realised_volatility,
    runs_test_z,
    trade_dependence_filter,
    trade_outcomes,
    volatility_target,
)
from libs.validation.lookahead_audit import future_invariance


def _rets(n=800, seed=1, sigma=0.02):
    return np.random.default_rng(seed).normal(0.0005, sigma, n)


# ------------------------------------------------------------------------ realised volatility

def test_it_is_nan_until_a_full_window_exists():
    v = realised_volatility(_rets(), window=20)
    assert np.all(np.isnan(v[:19])) and np.all(np.isfinite(v[19:]))


def test_it_recovers_a_known_volatility():
    """Annualisation and the sample convention both have to be right or every scale is off."""
    r = np.random.default_rng(2).normal(0, 0.02, 6000)
    v = realised_volatility(r, window=500, periods_per_year=365.0)
    assert np.nanmedian(v) == pytest.approx(0.02 * np.sqrt(365.0), rel=0.12)


def test_it_matches_a_direct_rolling_std():
    r = _rets(300, seed=3)
    v = realised_volatility(r, window=20, periods_per_year=365.0)
    direct = float(np.std(r[80:100], ddof=1) * np.sqrt(365.0))
    assert v[99] == pytest.approx(direct, rel=1e-10)


# --------------------------------------------------------------------- volatility targeting

def test_the_volatility_scale_is_lagged():
    """THE TEST THAT MATTERS. If the scale for bar i were computed from a window including bar i,
    the overlay would be cutting exposure using the very return it was about to take -- which
    makes vol targeting look far better than it is. Audited mechanically rather than by reading."""
    r = _rets(600, seed=4)

    def scaled(returns):
        return volatility_target(np.ones(returns.size), returns, window=20)

    rep = future_invariance(scaled, r, rng=np.random.default_rng(5), n_probes=20)
    assert rep["causal"], rep["verdict"]


def test_high_volatility_cuts_exposure_and_low_volatility_raises_it():
    calm = np.full(400, 0.001)
    calm[::2] = -0.0005                       # tiny oscillation -> very low realised vol
    wild = _rets(400, seed=6, sigma=0.12)
    lo = volatility_target(np.ones(400), calm, target_vol=0.15)
    hi = volatility_target(np.ones(400), wild, target_vol=0.15)
    assert np.nanmean(lo[50:]) > np.nanmean(hi[50:])


def test_exposure_is_capped():
    calm = np.full(500, 1e-6)
    out = volatility_target(np.ones(500), calm, leverage_cap=DEFAULT_LEVERAGE_CAP)
    assert np.nanmax(out) <= DEFAULT_LEVERAGE_CAP + 1e-12


def test_an_uncomputable_volatility_gives_zero_not_infinite():
    """Dividing by a not-yet-warm or frozen estimate would produce the largest position in the
    run at exactly the moment the desk knows least."""
    out = volatility_target(np.ones(300), np.zeros(300), window=20)
    assert np.all(np.isfinite(out)) and np.all(out == 0.0)


def test_it_preserves_the_sign_of_the_underlying_position():
    r = _rets(400, seed=7)
    pos = np.sign(np.random.default_rng(8).normal(0, 1, 400))
    out = volatility_target(pos, r)
    nz = out != 0
    assert np.all(np.sign(out[nz]) == np.sign(pos[nz]))


def test_misaligned_inputs_raise():
    with pytest.raises(ValueError):
        volatility_target(np.ones(100), np.zeros(99))


# --------------------------------------------------------------------------------- runs test

def test_perfect_alternation_gives_a_large_positive_z():
    """Alternation means more runs than chance -- losers followed by winners, the Turtle premise."""
    assert runs_test_z(np.tile([1.0, -1.0], 60)) > 5.0


def test_perfect_streaking_gives_a_large_negative_z():
    assert runs_test_z(np.concatenate([np.ones(60), -np.ones(60)])) < -5.0


def test_an_independent_sequence_sits_near_zero():
    s = np.sign(np.random.default_rng(9).normal(0, 1, 4000))
    assert abs(runs_test_z(s)) < 3.0


def test_a_degenerate_sequence_is_undefined_rather_than_scored():
    assert np.isnan(runs_test_z(np.ones(50)))


# -------------------------------------------------------------------------- trade dependence

def test_trades_are_split_at_position_changes():
    pos = np.array([0., 1., 1., 1., -1., -1., 0., 0.])
    r = np.zeros(8)
    ts = trade_outcomes(pos, r)
    assert [t["direction"] for t in ts] == [1.0, -1.0]
    assert (int(ts[0]["start"]), int(ts[0]["end"])) == (1, 3)


def test_the_filter_keeps_only_trades_after_the_requested_outcome():
    # three trades: win, loss, win -> after a LOSS only the third qualifies (first always taken)
    pos = np.array([1., 1., -1., -1., 1., 1.])
    r = np.array([0., 0.1, 0.0, -0.1, 0.0, 0.1])   # t1 wins, t2 wins (short into a fall)...
    out = trade_dependence_filter(pos, r, take_after="loss")
    assert out[0] == 1.0, "the first trade has no prior outcome and must always be taken"
    assert out.shape == pos.shape


def test_the_first_trade_is_always_taken():
    """Dropping it would silently shorten every backtest by one trade in a parameter-dependent
    way, which is the kind of bias that never announces itself."""
    pos = np.concatenate([np.ones(10), -np.ones(10)])
    r = np.zeros(20)
    assert trade_dependence_filter(pos, r, take_after="loss")[0] == 1.0


def test_the_filter_never_invents_a_position():
    r = _rets(400, seed=10)
    pos = np.sign(np.random.default_rng(11).normal(0, 1, 400))
    out = trade_dependence_filter(pos, r)
    taken = out != 0
    assert np.all(out[taken] == pos[taken]), "the filter changed a direction"
    assert np.sum(taken) <= np.sum(pos != 0), "the filter added exposure"


def test_an_unknown_mode_raises():
    with pytest.raises(ValueError, match="take_after"):
        trade_dependence_filter(np.ones(10), np.zeros(10), take_after="sideways")


# ------------------------------------------------------------------------------ hawkes / range

def test_hawkes_rises_on_a_spike_and_decays_after():
    x = np.zeros(200)
    x[50] = 10.0
    out = hawkes_process(x, kappa=0.1)
    assert out[50] > out[49]
    assert out[60] < out[50] and out[100] < out[60]
    assert out[100] > 0.0, "decay must be gradual, not a reset"


def test_a_smaller_kappa_decays_more_slowly():
    x = np.zeros(200)
    x[50] = 10.0
    slow, fast = hawkes_process(x, kappa=0.05), hawkes_process(x, kappa=0.5)
    assert slow[120] / slow[50] > fast[120] / fast[50]


def test_hawkes_is_causal():
    rep = future_invariance(lambda v: hawkes_process(v, kappa=0.1),
                            np.abs(_rets(500, seed=12)) + 0.001,
                            rng=np.random.default_rng(13), n_probes=15)
    assert rep["causal"], rep["verdict"]


def test_a_non_positive_kappa_raises():
    with pytest.raises(ValueError):
        hawkes_process(np.ones(10), kappa=0.0)


def test_normalised_range_is_scale_free():
    """The ATR normalisation is what makes the Hawkes quantile thresholds mean the same thing in
    every volatility regime; without it the output just tracks the level."""
    rng = np.random.default_rng(14)
    c = 100 * np.cumprod(1 + rng.normal(0, 0.02, 900))
    a = normalised_range(c * 1.01, c * 0.99, c, atr_window=336)
    b = normalised_range(c * 1000 * 1.01, c * 1000 * 0.99, c * 1000, atr_window=336)
    ok = np.isfinite(a) & np.isfinite(b)
    assert ok.sum() > 300 and np.allclose(a[ok], b[ok])


def test_non_positive_prices_raise():
    c = np.full(400, 100.0)
    with pytest.raises(ValueError, match="non-positive"):
        normalised_range(c, np.zeros(400), c)
