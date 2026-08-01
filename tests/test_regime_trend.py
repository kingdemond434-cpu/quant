"""Properties of the 2026-08-01 transcript mechanisms.

Two of these tests exist because the first version of the module was wrong in ways that looked
fine: test_divergence_is_actually_sparse (the threshold was comparing a fraction against a clipped
t-statistic, so it fired on ~87% of bars while being named "divergence") and
test_regime_labels_use_only_trailing_history (ranking a bar against the whole sample is the
in-sample leak that makes every regime study look better than it is).
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research import regime_trend as rt
from libs.research import transcript_candidates as tc


def _series(mu: float, sd: float, n: int = 900, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.cumprod(1.0 + rng.normal(mu, sd, n)) * 100.0


# ------------------------------------------------------------------ occupancy vs displacement

def test_occupancy_ignores_magnitude_entirely():
    """The defining property. If magnitude leaked in, this would be a slow momentum signal and
    would carry no information the desk does not already hold."""
    up = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    # Same sequence of SIGNS, wildly different magnitudes.
    up2 = np.array([100.0, 100.01, 130.0, 130.01, 131.0, 180.0])
    assert rt.time_in_direction(up, n=5)[-1] == pytest.approx(rt.time_in_direction(up2, n=5)[-1])


def test_occupancy_disagrees_with_displacement_on_the_configuration_it_targets():
    """A long quiet drift up, then one violent down bar big enough to flip cumulative return
    negative. Occupancy must stay bullish -- that disagreement IS the hypothesis."""
    c = np.concatenate([np.linspace(100.0, 110.0, 59), [70.0]])
    assert rt.time_in_direction(c, n=60)[-1] > 0.0, "occupancy should still read bullish"
    assert c[-1] < c[0], "while displacement over the same window is negative"


def test_occupancy_is_bounded_and_signed():
    for mu, sd in ((0.002, 0.01), (-0.002, 0.03), (0.0, 0.02)):
        p = rt.time_in_direction(_series(mu, sd, seed=1))
        assert np.all(np.abs(p) <= 1.0)
        assert np.all(np.isfinite(p))


def test_divergence_is_actually_sparse():
    """Named after what it does. The first implementation fired on ~87% of bars because it
    compared an up-bar FRACTION (bounded ~+/-0.3 in practice) against a CLIPPED t-statistic
    (saturating at +/-1) -- it was measuring the scale mismatch, not disagreement."""
    rates = []
    for i, (mu, sd) in enumerate(((0.0015, 0.010), (-0.002, 0.035), (0.0, 0.02))):
        d = rt.occupancy_divergence(_series(mu, sd, seed=i))
        rates.append(float(np.mean(d[60:] != 0.0)))
    assert max(rates) < 0.10, f"divergence fires on {max(rates):.1%} of bars -- not a divergence"


def test_divergence_only_ever_takes_the_occupancy_side():
    """It is a MASK over occupancy, never an independent signal. If it could take a position
    occupancy does not, a result would not be attributable to the divergence hypothesis."""
    c = _series(0.001, 0.02, seed=4)
    occ, div = rt.time_in_direction(c), rt.occupancy_divergence(c)
    nz = div != 0.0
    assert np.allclose(div[nz], occ[nz])


# ------------------------------------------------------------------------- the quadrant grid

def test_regime_labels_use_only_trailing_history():
    """Prefix invariance. A bar's label must not change when future bars are appended -- if it
    does, the classification is using information no live system could have."""
    c = _series(0.001, 0.02, n=1200, seed=5)
    full = rt.vol_trend_quadrant(c)
    part = rt.vol_trend_quadrant(c[:800])
    assert np.array_equal(full[:800], part)


def test_unclassifiable_bars_are_marked_not_guessed():
    c = _series(0.001, 0.02, n=400, seed=6)
    q = rt.vol_trend_quadrant(c, lookback=252)
    assert (q[:252] == -1).all(), "bars without enough history must be -1, never a default label"


def test_every_label_is_in_range():
    q = rt.vol_trend_quadrant(_series(0.0, 0.03, n=1500, seed=7))
    assert set(np.unique(q)).issubset(set(range(-1, 9)))
    assert len(rt.quadrant_labels) == 9


def test_the_asymmetry_exclusion_actually_fires_on_a_high_vol_bear():
    """The mechanism claims high-vol DOWNTRENDS are the losing cell. If the exclusion never
    triggers, the candidate is silently identical to its parent and tests nothing."""
    c = _series(-0.002, 0.035, n=1200, seed=8)
    occ, asym = rt.time_in_direction(c), rt._asymmetric_vol_trend(c)
    assert int(np.sum((occ != 0.0) & (asym == 0.0))) > 0


# ---------------------------------------------------------------------------- conviction gate

def test_conviction_gate_can_only_remove_exposure():
    """A filter that could ADD or FLIP a position would confound its own test -- a worse result
    could then mean 'the gate is wrong' or 'the new trades are bad'. Strict reduction makes a
    negative result a clean refutation."""
    c = _series(0.001, 0.02, n=1000, seed=9)
    p = rt.time_in_direction(c)
    g = rt.conviction_gate(p)
    assert np.all(np.abs(g) <= np.abs(p) + 1e-12)
    assert np.all((g == 0.0) | (np.sign(g) == np.sign(p)))


def test_conviction_gate_removes_something():
    c = _series(0.001, 0.02, n=1000, seed=10)
    p = rt.time_in_direction(c)
    assert int(np.sum((p != 0.0) & (rt.conviction_gate(p) == 0.0))) > 0


def test_conviction_gate_uses_only_trailing_history():
    c = _series(0.001, 0.02, n=1400, seed=11)
    p = rt.time_in_direction(c)
    assert np.array_equal(rt.conviction_gate(p)[:900], rt.conviction_gate(p[:900]))


# ------------------------------------------------------------------------------- integration

def test_every_candidate_produces_scorable_returns():
    c = _series(0.0012, 0.018, n=1200, seed=12)
    for name, fn in rt.CANDIDATES.items():
        pos = fn(c)
        assert len(pos) == len(c), name
        assert np.all(np.isfinite(pos)), name
        r = tc.positions_to_returns(pos, c)
        assert np.all(np.isfinite(r)), name


def test_positions_never_use_the_current_bars_own_return():
    """positions_to_returns applies pos[i] to bar i+1. A candidate that peeked would show a
    perfect fit on a series whose next move is deterministic; this checks the weaker, sufficient
    property that truncating the series does not change earlier positions."""
    c = _series(0.001, 0.02, n=1000, seed=13)
    for name, fn in rt.CANDIDATES.items():
        assert np.allclose(fn(c)[:700], fn(c[:700]), equal_nan=True), name
