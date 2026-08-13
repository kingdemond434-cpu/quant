"""L1.62 -- the screen's cross-sectional power denominator is MEASURED, or it refuses.

Every test here fails if the wiring is removed. The three that matter most are the ones pinning
the DIRECTION of each failure mode, because both endpoints of this error have been live on this
desk within one change of each other:

  * an unmeasured panel keeps the CONSERVATIVE full-K divisor (never the loose one), and
  * an unmeasured panel can never be `powered`, so it can never bank a graveyard-grade refutation
  * a measured panel gets its own number, which is near NEITHER endpoint.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.axis_screen import SCREEN_WARMUP_ROWS, stage_a_screen
from libs.research.cohort_independence import demeaning_floor
from libs.research.panel_breadth import (
    breadth_deflator,
    measure_panel_breadth,
)
from libs.validation.type2_cost import correlation_n_eff


def _noise(n: int = 1200, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.normal(size=n), rng.normal(0, 0.02, size=n)


def _panel(n_dates: int = 800, k: int = 40, rho: float = 0.0,
           seed: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """A (dates x symbols) product panel whose cross-sectional correlation is CONTROLLED.

    A common factor with loading sqrt(rho) on every name gives pairwise correlation rho, so the
    expected breadth is known in closed form and the estimator can be checked against it rather
    than against itself.
    """
    rng = np.random.default_rng(seed)
    common = rng.normal(size=(n_dates, 1))
    idio = rng.normal(size=(n_dates, k))
    sig = np.sqrt(rho) * common + np.sqrt(max(1.0 - rho, 0.0)) * idio
    tgt = rng.normal(size=(n_dates, k))
    return sig, tgt


# --------------------------------------------------------------- the estimator

def test_independent_panel_measures_near_full_breadth():
    """K independent names carry ~K bets per date -- the estimator must not invent dependence."""
    sig = np.random.default_rng(1).normal(size=(900, 30))
    tgt = np.random.default_rng(2).normal(size=(900, 30))
    b = measure_panel_breadth(sig, tgt)
    assert b.measured
    assert b.n_symbols == 30
    assert b.xs_neff > 20                      # near 30, well clear of 1
    assert abs(b.mean_corr) < 0.05


def test_a_single_common_factor_collapses_breadth():
    """The opposite endpoint: heavily shared structure must collapse to a handful of bets.

    This is the direction that PROTECTS the desk -- if a panel really is one bet in K costumes,
    the measurement has to say so, or this module would only ever loosen.
    """
    rng = np.random.default_rng(5)
    common = rng.normal(size=(900, 1))
    sig = np.tile(common, (1, 25)) + 0.05 * rng.normal(size=(900, 25))
    tgt = np.tile(common, (1, 25)) + 0.05 * rng.normal(size=(900, 25))
    b = measure_panel_breadth(sig, tgt)
    assert b.measured
    assert b.mean_corr > 0.5
    assert b.xs_neff < 3                       # 25 names, ~1 bet
    assert b.deflator > 8                      # so the divisor stays large, correctly


def test_breadth_is_bounded_by_the_symbols_that_exist():
    """`effective_bets` clamps to [1, K]: no arrangement of K names is more than K bets.

    The unclamped formula returned "64.4 independent bets from 29 perps" once, because removing a
    common factor forces residual correlation NEGATIVE by construction. Pinned here because this
    module's whole job is to raise a denominator, and an unbounded raise is the over-claim.
    """
    sig, tgt = _panel(n_dates=600, k=20, rho=0.0, seed=11)
    b = measure_panel_breadth(sig, tgt)
    assert 1.0 <= b.xs_neff <= 20.0
    assert b.deflator >= 1.0
    assert b.floor == pytest.approx(demeaning_floor(b.n_symbols))


@pytest.mark.parametrize("bad", ["one_column", "shape_mismatch", "all_nan", "not_2d"])
def test_unmeasurable_panels_refuse_rather_than_guess(bad: str):
    """UNMEASURED IS A REAL ANSWER (L1.28a). None of these may return a number."""
    if bad == "one_column":
        s = t = np.ones((50, 1))
    elif bad == "shape_mismatch":
        s, t = np.ones((50, 3)), np.ones((49, 3))
    elif bad == "all_nan":
        s = t = np.full((300, 5), np.nan)
    else:
        s = t = np.ones(50)
    b = measure_panel_breadth(s, t)
    assert b.status == "UNMEASURABLE"
    assert not b.measured
    assert b.why                                   # a refusal must say why
    assert not np.isfinite(b.xs_neff)


def test_every_dropped_column_is_counted():
    """L1.60: a column may leave the denominator, but never invisibly."""
    rng = np.random.default_rng(9)
    sig = rng.normal(size=(400, 10))
    tgt = rng.normal(size=(400, 10))
    sig[:, 0] = np.nan                             # too sparse
    tgt[:, 1] = 0.0                                # zero variance in the product
    b = measure_panel_breadth(sig, tgt)
    assert b.measured
    assert b.n_symbols_declared == 10
    assert b.n_symbols < 10
    assert sum(b.dropped.values()) >= 1
    assert b.dropped["too_few_obs"] >= 1
    # the declared width still drives the deflator: a dropped column contributes no evidence and
    # must not silently shrink the correction
    assert b.deflator == pytest.approx(10.0 / b.xs_neff, rel=1e-6)


# --------------------------------------------------------------- the deflator helper

def test_unmeasured_breadth_keeps_the_conservative_divisor():
    """THE REFUSAL DIRECTION. None must give back the full K, never 1 and never a guess."""
    assert breadth_deflator(139, None) == 139.0
    assert breadth_deflator(139, float("nan")) == 139.0
    assert breadth_deflator(139, 0.0) == 139.0     # a sub-1 breadth is not a licence to loosen
    assert breadth_deflator(1, None) == 1.0


def test_measured_breadth_lands_between_the_two_endpoints():
    assert breadth_deflator(139, 93.0) == pytest.approx(139 / 93.0)
    assert breadth_deflator(139, 139.0) == pytest.approx(1.0)   # fully independent
    assert breadth_deflator(139, 1.0) == pytest.approx(139.0)   # one bet -- the old assumption
    # never a MULTIPLIER, whatever it is handed
    assert breadth_deflator(10, 1e9) >= 1.0


# --------------------------------------------------------------- the harness wiring

def test_panel_without_measured_breadth_is_bit_identical_to_before():
    """Every existing caller must be untouched: the fix may not move a number by itself."""
    sig, ret = _noise(n=1390)
    r = stage_a_screen(sig, ret, name="panel", panel_width=139)
    assert r["breadth_basis"] == "UNMEASURED"
    assert r["xs_neff"] is None
    # against the harness's OWN scored row count, which is n - SCREEN_WARMUP_ROWS: the first 20
    # rows seed the rolling z and the last has no forward target.
    assert r["n"] == 1390 - SCREEN_WARMUP_ROWS
    assert r["n_eff"] == pytest.approx(r["n"] / 139, rel=0.01)


def test_measured_breadth_raises_effective_n_by_exactly_the_measured_factor():
    sig, ret = _noise(n=1390)
    assumed = stage_a_screen(sig, ret, name="a", panel_width=139)
    meas = stage_a_screen(sig, ret, name="m", panel_width=139, xs_neff=93.0)
    assert meas["breadth_basis"] == "MEASURED"
    assert meas["xs_neff"] == 93.0
    assert meas["n_eff"] / assumed["n_eff"] == pytest.approx(93.0, rel=0.02)
    assert meas["min_detectable_ic"] < assumed["min_detectable_ic"]
    assert meas["ic"] == assumed["ic"]              # power only -- never touches the estimate


def test_an_unmeasured_panel_can_never_be_powered():
    """THE LOAD-BEARING RAIL. `powered` licenses SCREEN-WEAK, the only graveyard-grade verdict.

    A refutation banked on an ASSUMED sample size is the false-null direction no other gate
    catches -- it is what produced the 42 SCREEN-WEAK verdicts the screen lacked the power to
    make. n=600k symbol-days over K=139 clears the ic_min floor arithmetically; without a
    measured basis it must still refuse to certify.
    """
    sig, ret = _noise(n=600_000)
    r = stage_a_screen(sig, ret, name="huge-unmeasured", panel_width=139, overlap_periods=1.0)
    assert r["n_eff"] > 4268                        # arithmetically powered ...
    assert r["min_detectable_ic"] <= 0.03
    assert r["powered"] is False                    # ... and still refused
    assert r["verdict"] != "SCREEN-WEAK"
    assert r["verdict"] == "SCREEN-UNDERPOWERED"

    same = stage_a_screen(sig, ret, name="huge-measured", panel_width=139,
                          overlap_periods=1.0, xs_neff=93.0)
    assert same["powered"] is True                  # the measurement is what unlocks it


def test_single_series_is_never_labelled_unmeasured():
    """A 1-wide 'panel' has nothing to measure; it must not be dragged into the refusal path."""
    sig, ret = _noise(n=5000)
    r = stage_a_screen(sig, ret, name="single")
    assert r["breadth_basis"] == "SINGLE-SERIES"
    assert r["xs_deflator"] == 1.0
    assert r["powered"] is True                     # unchanged behaviour for every single series


def test_breadth_composes_with_the_time_axis_deflator():
    """The two corrections are independent and must not cancel (2026-08-04 product-clamp bug)."""
    sig, ret = _noise(n=8000)
    r = stage_a_screen(sig, ret, name="p", horizon_days=20, panel_width=100,
                       overlap_periods=5.0, xs_neff=50.0)
    # time deflator 5, breadth deflator 100/50 = 2 -> 10x total
    assert r["n_eff"] == pytest.approx(8000 / 10.0, rel=0.01)


def test_sub_daily_breadth_still_cannot_manufacture_observations():
    sig, ret = _noise(n=900)
    r = stage_a_screen(sig, ret, name="tape", horizon_days=60 / 86400.0, panel_width=45,
                       xs_neff=45.0)
    assert r["n_eff"] <= 900


# --------------------------------------------------------------- the second copy of the expression

def test_type2_cost_agrees_with_the_harness():
    """`correlation_n_eff` is a deliberate COPY of the harness expression, so it must not drift.

    One bug in two files means fixing one leaves the other authoritative -- and this copy feeds
    the desk's published Type-II power figures.
    """
    assert correlation_n_eff(1000.0, panel_width=139) == pytest.approx(1000.0 / 139.0)
    assert correlation_n_eff(1000.0, panel_width=139, xs_neff=93.0) == pytest.approx(
        1000.0 / (139.0 / 93.0))
    # THE TWO COPIES MUST AGREE ON IDENTICAL INPUTS -- and "identical" means the harness's own
    # scored row count `n` (= raw length - SCREEN_WARMUP_ROWS), not the raw series length. That is
    # exactly what run_type2_report.py feeds it (`n_obs=cell["n"]`); passing the raw length here
    # instead would have this test assert a disagreement the live path does not have.
    sig, ret = _noise(n=1390)
    h = stage_a_screen(sig, ret, name="h", panel_width=139, overlap_periods=1.0, xs_neff=93.0)
    assert correlation_n_eff(float(h["n"]), horizon_periods=1.0, panel_width=139,
                             xs_neff=93.0) == pytest.approx(h["n_eff"], rel=0.01)


def test_type2_cost_unmeasured_is_unchanged():
    assert correlation_n_eff(1000.0, panel_width=139, xs_neff=None) == pytest.approx(
        correlation_n_eff(1000.0, panel_width=139))


def test_the_type2_reader_cannot_manufacture_a_disagreement():
    """L1.61: the recompute must use the divisor the SCREEN used, or it invents contradictions.

    `run_type2_report` re-derives `powered` from a recorded cell and labels a mismatch against the
    recorded flag DISAGREES. Before `xs_neff` was threaded through `correlation_negative`, that
    recompute used the full-K divisor while the screen had used the measured one, so EVERY
    measured panel cell (32 of them on the first run) would have been labelled a disagreement --
    a contradiction created by the reader rather than found by it, on the cells least able to
    defend themselves.
    """
    from libs.validation.type2_cost import correlation_negative

    sig, ret = _noise(n=8000)
    screened = stage_a_screen(sig, ret, name="cell", panel_width=100, overlap_periods=1.0,
                              xs_neff=50.0)
    assert screened["breadth_basis"] == "MEASURED"

    reread = correlation_negative(
        "cell", n_obs=float(screened["n"]),
        horizon_periods=float(screened["overlap_periods"]),
        panel_width=int(screened["panel_width"]), xs_neff=screened["xs_neff"])
    assert reread.n_eff == pytest.approx(screened["n_eff"], rel=0.01)

    # and dropping the breadth reproduces the disagreement, so this test fails if the wiring goes
    blind = correlation_negative(
        "cell", n_obs=float(screened["n"]),
        horizon_periods=float(screened["overlap_periods"]),
        panel_width=int(screened["panel_width"]))
    assert blind.n_eff < screened["n_eff"] / 10
