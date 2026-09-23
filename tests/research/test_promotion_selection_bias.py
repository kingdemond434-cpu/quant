"""R0574 -- pins the study's instrument and the decomposition its own null control forced.

The first version of `study_promotion_selection_bias` compared the desk's sizing directly against
an empirical-Bayes posterior mean and read the whole gap as the promotion winner's curse. It was
not: promoting a cohort member AT RANDOM showed the same gap, because the posterior mean was also
winning on the desk's spike-at-zero prior, which `S^2/(S^2+SE^2)` never shrinks toward. The tests
below fail against that design and pass against the one that isolates the selection term.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.risk.kelly_shrink import sharpe_se, shrink_fraction
from scripts import study_promotion_selection_bias as study


def test_vectorized_copies_match_the_live_library() -> None:
    """THE LOAD-BEARING INSTRUMENT CHECK. The study re-implements the sizer's SE and shrink in
    numpy; if `libs/risk/kelly_shrink` ever changes and this copy does not, every number the study
    publishes is about a sizer the desk no longer runs."""
    instr = study._instrument_checks()
    assert instr["instrument_ok"] is True, instr

    grid = np.array([0.1, 0.5, 1.0, 2.3, 4.0, 7.5])
    for n in (40.0, 90.0, 180.0, 365.0):
        assert study._se_vec(grid, n) == pytest.approx(
            [sharpe_se(float(s), n) for s in grid], rel=1e-12)
        assert study._shrink_vec(grid, n) == pytest.approx(
            [shrink_fraction(float(s), n) for s in grid], abs=1e-4)


def test_shrink_vec_reproduces_the_zero_branches() -> None:
    """`shrink_fraction` returns 0 for S<=0 and for n_eff<5, and the study must not size on a
    negative Sharpe just because it vectorized the happy path."""
    s = np.array([-2.0, -0.001, 0.0, 1.0])
    assert list(study._shrink_vec(s, 180.0)[:3]) == [0.0, 0.0, 0.0]
    assert study._shrink_vec(s, 180.0)[3] > 0.0
    assert list(study._shrink_vec(np.array([1.0, 2.0]), 4.0)) == [0.0, 0.0]


def test_growth_is_maximized_at_full_kelly() -> None:
    """The oracle arm sizes L = S_true and is only a genuine ceiling if that is the optimum."""
    s_true = 1.4
    lev = np.linspace(0.0, 4.0, 4001)
    g = study._growth(lev, np.full_like(lev, s_true))
    assert lev[int(np.argmax(g))] == pytest.approx(s_true, abs=2e-3)


def test_apply_clips_instead_of_extrapolating() -> None:
    """An unclipped map would let a Sharpe past the calibrated range invent leverage from a
    straight-line extension of the last bin -- exactly where the data is thinnest."""
    centre = np.array([0.5, 1.0, 1.5])
    target = np.array([0.1, 0.4, 0.9])
    out = study._apply(centre, target, np.array([-5.0, 0.0, 1.0, 50.0]))
    assert out[-1] == pytest.approx(0.9)           # clipped at the top bin, not extrapolated
    assert out[0] >= 0.0                            # never negative leverage
    assert out[2] == pytest.approx(0.4)


def test_null_control_leaves_no_selection_term() -> None:
    """THE TEST THAT PINS THE CORRECTION.

    With random promotion there is no selection, so the aware and blind maps see the same
    distribution and the selection term must vanish. The superseded design -- desk versus a single
    de-biased arm -- measured 0.98 of oracle growth on exactly this cell and would fail here.
    """
    c = study.cell(study.MAX_FORWARD_SLOTS, 180.0, 0.15, 1.0,
                   null_control=True, seed=11, rounds=40_000)
    assert c["promotion_rate"] == 1.0                      # no bar in the null control
    assert abs(c["selection_gain_as_frac_of_oracle"]) < 0.01, c
    assert str(c["verdict"]).startswith("NULL-CONTROL-PASSED"), c["verdict"]
    # and the PRIOR term is large on the same cell -- that is the effect the old design mistook
    # for selection, and keeping it visible is what stops the two being merged again
    assert c["prior_gain_as_frac_of_oracle"] > 0.1, c


def test_selection_bias_is_present_and_detected_under_real_selection() -> None:
    """The positive-control direction: with max-taking plus a Holm bar the selected estimate is
    upward-biased, and the aware map must find it. A method only ever shown to be silent has not
    been validated."""
    c = study.cell(study.MAX_FORWARD_SLOTS, 180.0, 0.15, 1.0, seed=11, rounds=40_000)
    assert c["selected_sharpe_bias_in_ses"] > 1.0, c       # winners really are inflated
    assert c["selection_gain_t"] > 3.0, c
    assert c["ceiling_holds"] is True, c


def test_ceiling_holds_in_every_arm() -> None:
    """The oracle sizes on S_true, so no arm may beat it. A cell that does is a broken simulator
    and its gammas mean nothing (the convention study_absorbing_kelly established)."""
    c = study.cell(4, 90.0, 0.05, 1.0, seed=3, rounds=20_000)
    means = c["mean_growth"]
    assert all(means["oracle"] >= means[k] - 1e-9 for k in
               ("naive", "desk", "eb_blind", "eb_aware")), means


def test_harvest_chunking_does_not_depend_on_the_cohort_size() -> None:
    """The chunking exists because the m=420 control was OOM-killed unchunked (exit 137).

    It is deliberately a constant number of ROUNDS: an element-budget chunk made the boundaries a
    function of `m`, so two cells of the same study consumed the generator differently for reasons
    unrelated to the question. Full invariance to `_CHUNK_ROUNDS` itself is NOT claimed -- changing
    it reshapes the draws -- so what is pinned here is the property that matters and is real:
    identical seeds reproduce exactly, and chunking introduces no distributional bias.
    """
    kw = {"rounds": 6_000, "m": 12, "pi": 0.15, "s_edge": 1.0, "n_days": 180.0,
          "bar": 2.64, "sel_rng": None}
    a = study._harvest(np.random.default_rng(5), **kw)            # type: ignore[arg-type]
    b = study._harvest(np.random.default_rng(5), **kw)            # type: ignore[arg-type]
    assert np.array_equal(a[0], b[0]) and np.array_equal(a[2], b[2])   # reproducible

    old = study._CHUNK_ROUNDS
    try:
        study._CHUNK_ROUNDS = 1_000_000       # one single chunk
        one = study._harvest(np.random.default_rng(5), **kw)      # type: ignore[arg-type]
    finally:
        study._CHUNK_ROUNDS = old
    # different draws, same distribution: winner means agree well inside Monte-Carlo error
    assert one[0].size == a[0].size
    assert float(one[0].mean()) == pytest.approx(float(a[0].mean()), abs=0.15)
    assert float(one[2].mean()) == pytest.approx(float(a[2].mean()), abs=0.03)
