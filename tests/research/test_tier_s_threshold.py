"""The Tier S t is DERIVED from the canonical deflated Sharpe, pinned on the auditor's figures.

Bar: `libs.validation.dsr.deflated_sharpe_ratio` at n_trials = bar_n() (= 5), null variance
1/(T-1), DSR >= 0.95. Auditor's figures under normal returns (2026-10-14): t about 4.56 at T=5,
3.06 at T=24, 2.89 at T=100, tending to about 2.84, and identical at any trial count.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pytest
from scipy.stats import kurtosis, skew

from libs.research import trial_count_guard as tcg
from libs.research.trial_count_guard import tier_s_passes, tier_s_t_required
from libs.validation.dsr import deflated_sharpe_ratio, expected_max_sharpe


@pytest.mark.parametrize(("n", "t"), [(5, 4.56), (24, 3.06), (100, 2.89)])
def test_the_auditors_figures_under_normal_returns(n: int, t: float) -> None:
    assert tier_s_t_required(n) == pytest.approx(t, abs=0.01)


def test_it_tends_to_about_2_84_from_above() -> None:
    seq = [tier_s_t_required(n) for n in (100, 1_000, 10_000, 1_000_000)]
    assert all(a > b for a, b in itertools.pairwise(seq)), "monotone toward the limit"
    assert seq[-1] == pytest.approx(2.84, abs=0.01)


def test_it_is_identical_at_any_trial_count() -> None:
    """The count a caller measured goes through bar_n and cannot move the bar: every pinned site
    (min(k, bar_n(k)) for k >= BAR_N, or bar_n(k) itself) reaches the helper's sr0 exactly."""
    from libs.research.tier_s_threshold import tier_s_sr0
    n = 250
    for k in (5, 109, 597, 234_977):
        assert expected_max_sharpe(min(k, tcg.bar_n(k)), 1.0 / (n - 1)) == tier_s_sr0(n)
        assert expected_max_sharpe(tcg.bar_n(k), 1.0 / (n - 1)) == tier_s_sr0(n)
    assert tier_s_t_required(n) / math.sqrt(n) > tier_s_sr0(n)


def test_the_helper_is_re_exported_and_derived_not_copied() -> None:
    from libs.research import tier_s_threshold as home
    assert tcg.tier_s_t_required is home.tier_s_t_required
    assert tcg.tier_s_passes is home.tier_s_passes
    assert tier_s_t_required(2) == math.inf


def _exact(n: int, t: float, seed: int = 7) -> np.ndarray:
    """A series of n periods whose sample t (mean/std x sqrt(n)) is exactly t."""
    z = np.random.default_rng(seed).standard_normal(n)
    z = (z - z.mean()) / z.std(ddof=1)
    return z + t / math.sqrt(n)


@pytest.mark.parametrize("n", [24, 100, 500])
def test_passes_agrees_with_the_threshold_on_the_canonical_function(n: int) -> None:
    """Just above the derived t (at the series' own skew/kurtosis) passes the canonical DSR;
    just below fails -- so the helper and the function cannot drift apart."""
    base = _exact(n, 0.0)
    g3, g4 = float(skew(base, bias=False)), float(kurtosis(base, fisher=False, bias=False))
    t = tier_s_t_required(n, skew=g3, kurtosis=g4)
    # shifting by a constant leaves skew and kurtosis unchanged
    up, down = _exact(n, t * 1.001), _exact(n, t * 0.999)
    ok_up, dsr_up = tier_s_passes(up)
    ok_down, dsr_down = tier_s_passes(down)
    assert ok_up and not ok_down
    assert dsr_down < 0.95 <= dsr_up
    ref = deflated_sharpe_ratio(up, n_trials=tcg.bar_n(), variance_of_sharpes=1.0 / (n - 1))
    assert ref.dsr == pytest.approx(dsr_up)


def test_a_fat_left_tail_demands_more() -> None:
    assert tier_s_t_required(250, skew=-1.0, kurtosis=8.0) > tier_s_t_required(250)


def test_too_short_a_series_never_passes() -> None:
    assert tier_s_passes([0.1]) == (False, 0.0)
