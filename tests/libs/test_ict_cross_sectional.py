"""BREADTH MUST BE MEASURED, AND THE HEDGE MUST NOT BE FITTED TO WHAT IT HEDGES.

The figure that motivated this module -- 2.08x IR from 25 symbols at an assumed residual
correlation of 0.2 -- was a PREMISE. Reporting it as a result would be the same error this desk
keeps finding in itself, one level up: a number nobody measured presented in the vocabulary of one
that was. So `effective_breadth` derives N_eff from the realised streams, and these tests pin it
against cases whose true answer is known by construction.

The beta tests matter just as much. A full-sample beta would hedge each position using covariance
that position helped produce, leaving an artificially clean residual and an artificially high
breadth -- the exact number this module exists to produce, manufactured by the leak.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.ict.cross_sectional import (
    HEDGE_BAND,
    _band_hold,
    effective_breadth,
    equal_weight_index,
    residualise,
    rolling_beta,
    run_cross_sectional,
)
from libs.ict.strategy import ICTParams


def _panel(n: int = 3000, k: int = 8, rho: float = 0.8, seed: int = 0) -> dict[str, pd.DataFrame]:
    """k symbols sharing a common factor at correlation `rho` -- the crypto shape."""
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.0035, n)
    out = {}
    for i in range(k):
        idio = rng.normal(0, 0.0035, n)
        r = np.sqrt(rho) * common + np.sqrt(1 - rho) * idio
        c = 100 * np.exp(np.cumsum(r))
        o = np.concatenate(([100.0], c[:-1]))
        w = np.abs(rng.normal(0, 0.0035, n)) * c
        out[f"S{i}"] = pd.DataFrame({"open": o, "high": np.maximum(o, c) + w,
                                     "low": np.minimum(o, c) - w, "close": c})
    return out


# ------------------------------------------------------- effective breadth

def test_independent_streams_measure_full_breadth() -> None:
    """N independent equal-vol streams must measure as exactly N. If the estimator cannot recover
    the easy case it cannot be trusted on the hard one."""
    rng = np.random.default_rng(0)
    d = pd.DataFrame(rng.normal(0, 1, (5000, 10)))
    n_eff, corr = effective_breadth(d)
    assert n_eff == pytest.approx(10, rel=0.1)
    assert abs(corr) < 0.05


def test_perfectly_correlated_streams_measure_as_one_bet() -> None:
    """Ten copies of the same stream are one bet, however many columns the report has."""
    rng = np.random.default_rng(1)
    base = rng.normal(0, 1, 3000)
    d = pd.DataFrame({f"c{i}": base for i in range(10)})
    n_eff, corr = effective_breadth(d)
    assert n_eff == pytest.approx(1.0, rel=0.02)
    assert corr == pytest.approx(1.0, rel=0.02)


def test_breadth_collapses_as_correlation_rises() -> None:
    """Monotonicity is the cheap check that the estimator responds to the thing it claims to."""
    rng = np.random.default_rng(2)
    prev = None
    for rho in (0.0, 0.4, 0.8, 0.95):
        common = rng.normal(0, 1, 4000)
        d = pd.DataFrame({f"c{i}": np.sqrt(rho) * common + np.sqrt(1 - rho)
                          * rng.normal(0, 1, 4000) for i in range(8)})
        n_eff, _ = effective_breadth(d)
        if prev is not None:
            assert n_eff <= prev + 0.3
        prev = n_eff


def test_too_short_a_sample_returns_nan_not_a_number() -> None:
    """A correlation on 5 observations is not a measurement, and returning one invites it to be
    quoted."""
    n_eff, corr = effective_breadth(pd.DataFrame(np.zeros((5, 3))))
    assert np.isnan(n_eff) and np.isnan(corr)


# ------------------------------------------------------------------- beta

def test_beta_is_causal() -> None:
    """THE LEAK THAT WOULD MANUFACTURE THE ANSWER. A full-sample beta hedges each position with
    covariance that position helped produce. Truncating the series must not change beta on the
    bars that survive."""
    rng = np.random.default_rng(3)
    idx = pd.Series(rng.normal(0, 0.01, 2000))
    sym = 1.3 * idx + pd.Series(rng.normal(0, 0.005, 2000))
    full = rolling_beta(sym, idx, 200).to_numpy()
    part = rolling_beta(sym.iloc[:1500], idx.iloc[:1500], 200).to_numpy()
    assert np.allclose(full[:1500], part, equal_nan=True)


def test_beta_recovers_a_known_loading() -> None:
    rng = np.random.default_rng(4)
    idx = pd.Series(rng.normal(0, 0.01, 4000))
    sym = 1.5 * idx + pd.Series(rng.normal(0, 0.002, 4000))
    assert float(rolling_beta(sym, idx, 300).iloc[-1]) == pytest.approx(1.5, rel=0.1)


def test_residualising_removes_the_common_factor() -> None:
    rng = np.random.default_rng(5)
    idx = pd.Series(rng.normal(0, 0.01, 4000))
    sym = 1.2 * idx + pd.Series(rng.normal(0, 0.004, 4000))
    b = rolling_beta(sym, idx, 300)
    res = residualise(sym, idx, b).iloc[400:]
    assert abs(float(res.corr(idx.iloc[400:]))) < abs(float(sym.corr(idx)))


def test_an_unknown_beta_hedges_one_for_one_rather_than_zero() -> None:
    """Defaulting to 0 leaves FULL market exposure in a book whose premise is having none -- the
    fail-open direction, on the one parameter that defines the strategy."""
    s = pd.Series([0.0] * 10)
    assert float(rolling_beta(s, s, 200).iloc[0]) == 1.0


# ------------------------------------------------------------- hedge band

def test_a_zero_band_reduces_to_continuous_rebalancing() -> None:
    d = pd.DataFrame(np.random.default_rng(6).normal(0, 1, (200, 3)))
    pd.testing.assert_frame_equal(_band_hold(d, 0.0), d)


def test_banding_reduces_turnover() -> None:
    """The whole reason it exists: a continuously-rebalanced hedge re-trades beta noise every bar,
    which measured 490% of capital a year in fees on the control panel."""
    d = pd.DataFrame(np.random.default_rng(7).normal(0, 1, (2000, 4)))
    assert (_band_hold(d, 0.5).diff().abs().sum().sum()
            < d.diff().abs().sum().sum())


def test_the_band_never_blocks_an_entry_or_an_exit() -> None:
    """THE FAIL-OPEN THIS TEST CAUGHT. The band was applied to every change including the first,
    so with a wide band the hedge was never put on at all -- a book reporting itself
    market-neutral while carrying full directional exposure. Opening from flat and returning to
    flat must always execute; only the drift in between may wait."""
    d = pd.DataFrame({"a": [1.0, 1.0, 0.0, 0.0]})
    assert list(_band_hold(d, 5.0)["a"]) == [1.0, 1.0, 0.0, 0.0]


def test_the_band_does_defer_a_mid_life_adjustment() -> None:
    """And it must still do the job it exists for, or it is just an expensive no-op."""
    d = pd.DataFrame({"a": [1.0, 1.1, 1.15, 2.0]})
    assert list(_band_hold(d, 0.5)["a"]) == [1.0, 1.0, 1.0, 2.0]


# --------------------------------------------------------------- the book

def test_hedging_raises_measured_breadth_on_a_correlated_panel() -> None:
    """THE CLAIM THE MODULE EXISTS TO TEST, on a panel whose common factor is known."""
    r = run_cross_sectional(_panel(rho=0.8), ICTParams())
    assert r.n_eff_residual > r.n_eff_directional
    assert abs(r.mean_corr_residual) < abs(r.mean_corr_directional) + 0.05


def test_costs_and_returns_come_off_the_same_book() -> None:
    """AN EARLIER VERSION SCALED P&L TO THE GROSS CAP AND CHARGED FEES ON UNSCALED POSITIONS,
    reporting 490%/yr for a book that was never that big. The error was PESSIMISTIC, which is
    exactly why it survived a reading -- a number that looks bad does not get questioned. Halving
    the cap must roughly halve the cost."""
    p = _panel()
    big = run_cross_sectional(p, ICTParams(), gross_cap=1.0).cost_drag_annual
    small = run_cross_sectional(p, ICTParams(), gross_cap=0.5).cost_drag_annual
    assert small < big
    assert small == pytest.approx(big / 2, rel=0.35)


def test_a_single_symbol_is_refused() -> None:
    """Running this on one symbol reports a market-neutral result for a directional bet."""
    with pytest.raises(ValueError, match="at least 2"):
        run_cross_sectional({"S0": _panel(k=1)["S0"]}, ICTParams())


def test_the_result_states_that_costs_are_a_lower_bound() -> None:
    """Market impact is not modelled. A cost estimate that does not say what it omits gets
    quoted as complete."""
    r = run_cross_sectional(_panel(), ICTParams())
    assert "LOWER BOUND" in r.note


def test_hedge_band_default_is_applied() -> None:
    p = _panel()
    assert (run_cross_sectional(p, ICTParams(), hedge_band=HEDGE_BAND).cost_drag_annual
            <= run_cross_sectional(p, ICTParams(), hedge_band=0.0).cost_drag_annual + 1e-9)


def test_equal_weight_index_is_built_from_the_panel() -> None:
    """A hedge against an instrument the desk does not hold is a second bet."""
    d = pd.DataFrame({"a": [0.01, -0.01], "b": [0.03, 0.01]})
    assert list(equal_weight_index(d)) == [0.02, 0.0]


def test_financing_is_charged_on_net_exposure_not_gross() -> None:
    """THE ONE LINE ITEM WHERE THE HEDGE PAYS FOR ITSELF. The overnight swap accrues per leg at
    each daily rollover: a long pays when the rate is against it, a short receives. Charged on
    GROSS it would double the drag and erase precisely the advantage a market-neutral book has;
    charged on NET, the hedged book is largely immune. Raising the rate five-fold must therefore
    barely move a neutral book."""
    p = _panel()
    zero = run_cross_sectional(p, ICTParams(), financing_bps_per_day=0.0).cost_drag_annual
    high = run_cross_sectional(p, ICTParams(), financing_bps_per_day=5.0).cost_drag_annual
    assert high >= zero
    assert (high - zero) < 0.05 * max(zero, 1e-9), (
        f"financing moved the hedged book's cost {zero:.3f} -> {high:.3f}; a market-neutral book "
        "should net most of it out, so this reads as financing being charged on gross")


def test_the_note_no_longer_claims_financing_is_unmodelled() -> None:
    """It was a stated gap; a stale caveat is as misleading as a missing one."""
    n = run_cross_sectional(_panel(), ICTParams()).note
    assert "financing IS " in n
    assert "Market impact is not modelled" in n, "and what remains missing must still be said"
