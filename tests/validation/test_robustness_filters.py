"""These filters must reject a PATHOLOGY and be silent on everything else.

The audit found this desk over-conservative, so any new rejection has to justify itself: it may
cost essentially no power against genuine edges, or it does not belong here.
"""
from __future__ import annotations

import numpy as np

from libs.validation.robustness_filters import (
    LUCK_Z,
    MIN_TRADES,
    REAL_EDGE_OOS_SHARPE_BAND,
    apply_all,
    asset_drift,
    not_too_lucky,
    sample_adequacy,
)


def test_sample_adequacy_rejects_the_fifteen_trade_kelly():
    """The live defect this exists for: an external walkthrough computed a full Kelly fraction
    from 15 trades over 33 years and sized real money from it."""
    assert not sample_adequacy(15).passed
    assert "carries no information" in sample_adequacy(15).why
    assert sample_adequacy(MIN_TRADES).passed
    assert sample_adequacy(500).passed


def test_a_real_edge_with_normal_degradation_is_untouched():
    """The design rule. In-sample is where parameters were chosen, so a real edge degrades out of
    sample -- that is expected and must never be penalised."""
    for oos in (0.4, 0.6, 0.8, 1.0, 1.2):
        assert not_too_lucky(1.2, oos, 217, 93).passed, f"penalised degradation at oos={oos}"


def test_only_an_improvement_beyond_sampling_noise_trips_the_luck_filter():
    """Studentised, so the bar scales with how noisy the two estimates actually are."""
    import numpy as np
    se = float(np.sqrt(365.0 / 217 + 365.0 / 93))
    assert not_too_lucky(1.0, 1.0 + (LUCK_Z - 0.1) * se, 217, 93).passed
    v = not_too_lucky(1.0, 1.0 + (LUCK_Z + 0.5) * se, 217, 93)
    assert not v.passed and "draws do not repeat" in v.why
    # AND THE DIRECTION A FIXED RATIO CANNOT EXPRESS: a MODEST absolute gap is invisible in a
    # short sample and damning in a long one, because the estimates get precise enough to resolve
    # it. Same +1.0 Sharpe gap, opposite verdicts -- driven by sample size, not by the gap.
    assert not_too_lucky(1.0, 2.0, 217, 93).passed          # +0.42 SE: cannot distinguish
    assert not not_too_lucky(1.0, 2.0, 4000, 4000).passed   # +2.34 SE: now it is real


def test_the_luck_filter_is_silent_when_in_sample_is_dead():
    """A non-positive in-sample Sharpe has no meaningful ratio, and expected_value/dsr already own
    that case -- firing here too would double-count one defect as two."""
    assert not_too_lucky(0.0, 3.0, 217, 93).passed
    assert not_too_lucky(-0.5, 3.0, 217, 93).passed
    assert "already own this case" in not_too_lucky(-0.5, 3.0, 217, 93).why


def test_asset_drift_reports_unmeasured_rather_than_passed():
    """THE POINT OF THIS ONE. validate()'s beats_baselines returns True when no benchmark is
    supplied, and no production caller supplies one -- measured 2026-08-01, it blocked 0.0% of
    pure asset-drift candidates. A gate counted as protection that never runs is worse than no
    gate. This reports the difference."""
    v = asset_drift(np.array([0.01, -0.01, 0.02]), None)
    assert v.passed                                   # does not block -- it cannot know
    assert "UNMEASURED" in v.why
    assert "evidence the check did not run" in v.why


def test_asset_drift_catches_pure_exposure_when_it_can_measure():
    rng = np.random.default_rng(3)
    bench = rng.standard_normal(400) * 0.01 + 0.0015   # a trending asset
    assert not asset_drift(bench.copy(), bench).passed  # buy-and-hold cannot beat itself
    better = bench + rng.standard_normal(400) * 0.002 + 0.0010
    assert asset_drift(better, bench).passed


def test_mismatched_benchmark_length_is_unmeasured_not_a_pass():
    v = asset_drift(np.zeros(100), np.zeros(50))
    assert "UNMEASURED" in v.why


def test_the_recorded_edge_band_is_below_what_the_desk_assumed():
    """Recorded because it reframes every power number in the audit: the desk was reasoning about
    'world-class = 2-3' while a 131,441-backtest sweep observed real verified edge at 0.5-1.5."""
    lo, hi = REAL_EDGE_OOS_SHARPE_BAND
    assert lo == 0.5 and hi == 1.5
    assert hi < 2.0


def test_apply_all_names_which_pathology_fired():
    # SE at 217/93 is ~2.37 annualised Sharpe, so the gap must clear ~4.7 to be implausible --
    # a 3.0-vs-1.0 gap is only +0.84 SE and SHOULD pass, which is the whole point of studentising
    assert apply_all(n_trades=200, is_sharpe=1.0, oos_sharpe=3.0,
                     n_is=217, n_oos=93)["not_too_lucky"].passed
    out = apply_all(n_trades=10, is_sharpe=1.0, oos_sharpe=8.0, n_is=217, n_oos=93)
    assert not out["sample_adequacy"].passed
    assert not out["not_too_lucky"].passed
    clean = apply_all(n_trades=200, is_sharpe=1.2, oos_sharpe=0.9, n_is=217, n_oos=93)
    assert all(v.passed for v in clean.values())
    assert "asset_drift" not in clean                 # not claimed when returns were not supplied
