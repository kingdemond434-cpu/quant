"""L1.48 wiring (2026-08-05): Stage-B eligibility asks evidence_clock, not a 40-day constant.

`_MIN_DAYS = 40` in run_axis_shadows was one of the sites evidence_clock's own docstring names as
the habit being killed. These tests pin the migrated behavior: the statistical bar (Newey-West t
vs the Holm cohort bar) is untouched; the flat observation wall is gone; a non-positive effect
fails at evidence_clock's trust floor instead of an arbitrary 40; and shortfalls are reported in
OBSERVATIONS, never days.
"""
from __future__ import annotations

import importlib

import numpy as np

from libs.research.evidence_clock import MIN_OBS
from libs.validation.forward_stats import nw_tstat

ras = importlib.import_module("scripts.run_axis_shadows")

_BAR = 2.64  # a realistic Holm bar for the 12-clock cohort; the tests pass it explicitly
_ALPHA = 0.05 / 12  # the SAME family-wise level _BAR encodes -- R0187 made it explicit at
                    # every call site so the two Stage-B gates can never drift apart.


def test_strong_axis_is_eligible_before_the_old_forty_obs_wall():
    """The fast book is no longer punished for being fast: overwhelming evidence at n=25
    (old code: ACCRUING until n=40 regardless of t) is ELIGIBLE now."""
    rng = np.random.default_rng(7)
    arr = rng.normal(0.02, 0.005, 25)          # enormous per-obs effect
    t = float(nw_tstat(arr))
    assert t >= _BAR, "fixture must clear the bar on its own merits"
    verdict, need, suff = ras._stage_b_verdict(arr, t, _BAR, alpha=_ALPHA)
    assert verdict == "ELIGIBLE"
    assert need == 25 and suff.sufficient


def test_nw_bar_still_binds_even_when_plain_t_passes():
    """Strict tightening: evidence_clock's plain t may pass while the autocorrelation-aware
    Newey-West t does not -- eligibility requires BOTH, so the bar never loosened."""
    rng = np.random.default_rng(11)
    arr = rng.normal(0.02, 0.005, 25)
    verdict, _, suff = ras._stage_b_verdict(arr, 1.0, _BAR, alpha=_ALPHA)   # NW t below bar
    assert suff.sufficient, "fixture: plain t clears the bar"
    assert verdict == "ACCRUING", "NW t under the bar must never grant ELIGIBLE"


def test_non_positive_effect_fails_at_the_trust_floor_not_at_forty():
    """A clearly failing clock (kimchi shape: negative t) is called FAILING once n >= MIN_OBS --
    the point evidence_clock says more data will not fix it -- not held ACCRUING to 40."""
    rng = np.random.default_rng(3)
    arr = rng.normal(-0.01, 0.008, MIN_OBS)
    t = float(nw_tstat(arr))
    assert t <= 0.0
    verdict, need, _ = ras._stage_b_verdict(arr, t, _BAR, alpha=_ALPHA)
    assert verdict == "FAILING"
    assert need == MIN_OBS


def test_weakly_positive_axis_accrues_with_shortfall_in_observations():
    """Old code called 0 < t < bar at n >= 40 'FAILING' -- conflating insufficiency with evidence
    against. Now it is ACCRUING and the payload states how many MORE OBSERVATIONS the current
    effect size needs (L1.48: report shortfalls in observations, never days)."""
    rng = np.random.default_rng(5)
    arr = rng.normal(0.001, 0.01, 60)
    t = float(nw_tstat(arr))
    if t <= 0.0 or t >= _BAR:                   # keep the fixture honest about its own regime
        arr = np.abs(arr) * 0.02 + 0.0001       # tiny positive drift, huge noise
        t = float(nw_tstat(arr))
    verdict, need, suff = ras._stage_b_verdict(arr, min(t, 1.0), _BAR, alpha=_ALPHA)
    assert verdict == "ACCRUING"
    assert need > arr.size, "shortfall must be expressed as MORE observations needed"
    assert "observation" in suff.reason


def test_below_trust_floor_is_always_accruing():
    arr = np.asarray([-0.01, -0.02, -0.015, -0.01, -0.02] * 2)   # n=10 < MIN_OBS, negative
    verdict, need, _ = ras._stage_b_verdict(arr, float(nw_tstat(arr)), _BAR, alpha=_ALPHA)
    assert verdict == "ACCRUING", "no verdict of failure below the observation trust floor"
    assert need == MIN_OBS


def test_the_calendar_constant_is_gone():
    """The offender L1.48's fence flagged (scripts/run_axis_shadows.py `_MIN_DAYS = 40`) must not
    quietly return."""
    assert not hasattr(ras, "_MIN_DAYS")
