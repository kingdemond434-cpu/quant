"""A trial count inflated by clones over-penalises every gate built on it.

The deflated Sharpe threshold scales with E[max of N trials], derived for N INDEPENDENT draws.
A sweep over (symbol x family x side x window x state x params) manufactures near-copies
structurally: rr=2.0/ttl=12 and rr=2.0/ttl=13 are one search sampled twice, not two searches.

This is live. The nine MT5 candidates fail the gauntlet on deflated Sharpe ALONE against
n_trials = 2,464, while passing PBO at 0.034 and walk-forward stability at 1.0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.canonical import (  # noqa: E402
    CLONE_RHO, calibrated_census_report, canonical_formula, census_report, deflation_pair,
    effective_trials, expected_max_z, fingerprint, null_calibrated_effective_trials)

RNG = np.random.default_rng(20260817)


def _indep(n, t=250):
    return [RNG.normal(size=t) for _ in range(n)]


# ------------------------------------------------------------------- structural

def test_algebraically_equivalent_expressions_fingerprint_identically():
    """(close-SMA20)/ATR20 written two ways is one hypothesis, not two."""
    assert canonical_formula("a + b") == canonical_formula("b + a")
    assert canonical_formula("x * y") == canonical_formula("y * x")
    assert canonical_formula("(close - sma20) / atr20") == canonical_formula(
        "(close-sma20)/atr20")


def test_float_and_int_literals_are_the_same_window():
    assert canonical_formula("sma(close, 20)") == canonical_formula("sma(close, 20.0)")


def test_genuinely_different_formulas_do_not_collide():
    assert canonical_formula("a - b") != canonical_formula("b - a")
    assert fingerprint("a+b") != fingerprint("a*b")


def test_the_same_formula_on_different_data_is_a_different_hypothesis():
    """Lineage is part of the identity: gold and CADJPY are two real searches."""
    assert fingerprint("a+b", data_lineage="XAUUSD.H1") != fingerprint(
        "a+b", data_lineage="CADJPY.H1")


def test_an_unparseable_expression_still_fingerprints_stably():
    assert fingerprint("this is not python((") == fingerprint("this is not python((")


# -------------------------------------------------------------------- functional

def test_identical_trials_count_as_one_search():
    """THE DEFECT. Twenty copies of one strategy is one search, and E[max of 20] would penalise
    it as if twenty independent bets had been tried."""
    base = RNG.normal(size=250)
    c = effective_trials([base.copy() for _ in range(20)])
    assert c.n_raw == 20
    assert c.n_effective == pytest.approx(2.0, abs=0.01), "clones counted as separate searches"
    assert c.inflation > 9


def test_independent_trials_are_not_discounted():
    """The other failure mode, and the dangerous one: discounting a genuinely wide search would
    hand out passes."""
    c = effective_trials(_indep(30))
    assert c.n_effective > 25, f"independent trials were discounted to {c.n_effective:.1f}"
    assert c.n_effective <= 30


def test_null_calibration_removes_the_estimators_finite_sample_floor():
    cols = _indep(30, t=90)
    raw = effective_trials(cols)
    calibrated = null_calibrated_effective_trials(cols)
    assert raw.n_effective < 30
    assert calibrated.n_effective >= raw.n_effective
    assert calibrated.n_effective > 27
    assert calibrated.method == "null_calibrated_participation_ratio"


def test_null_calibration_is_fixed_and_clone_sensitive():
    base = RNG.normal(size=120)
    cols = [base.copy() for _ in range(12)]
    first = null_calibrated_effective_trials(cols)
    second = null_calibrated_effective_trials(cols)
    assert first == second
    assert 2.0 <= first.n_effective <= 2.5


def test_two_tight_clusters_are_seen_as_two_searches_not_twelve():
    """Why the participation ratio and not a mean correlation: a mean collapses 'twelve mildly
    related cells' and 'two tight clusters of six' into the same number. A parameter sweep is
    always the second."""
    a, b = RNG.normal(size=250), RNG.normal(size=250)
    cols = [a + RNG.normal(size=250) * 0.02 for _ in range(6)]
    cols += [b + RNG.normal(size=250) * 0.02 for _ in range(6)]
    c = effective_trials(cols)
    assert 2.0 <= c.n_effective <= 3.5, f"12 cells in 2 clusters read as {c.n_effective:.1f}"


def test_n_effective_can_never_exceed_the_search_performed():
    for n in (2, 5, 30):
        assert effective_trials(_indep(n)).n_effective <= n


def test_n_effective_is_floored_at_two():
    base = RNG.normal(size=250)
    assert effective_trials([base.copy() for _ in range(50)]).n_effective >= 2.0


def test_clone_pairs_are_listed_for_audit():
    base = RNG.normal(size=250)
    c = effective_trials([base.copy(), base.copy(), RNG.normal(size=250)])
    assert any(abs(r) >= CLONE_RHO for _, _, r in c.clone_pairs)


def test_the_clone_threshold_does_not_move_n_effective():
    """CLONE_RHO is reporting only. If a threshold choice could move a gate, someone would tune
    it until the gate passed."""
    cols = [RNG.normal(size=250) for _ in range(8)]
    import mt5desk.canonical as C
    before = effective_trials(cols).n_effective
    old = C.CLONE_RHO
    try:
        C.CLONE_RHO = 0.10
        assert effective_trials(cols).n_effective == pytest.approx(before)
    finally:
        C.CLONE_RHO = old


# ------------------------------------------------------------------- fails closed

def test_an_unmeasurable_matrix_returns_the_raw_count():
    """ABSENCE OF EVIDENCE OF DUPLICATION IS NOT A DISCOUNT. Series too short to correlate must
    leave the threshold exactly where it was."""
    c = effective_trials([np.array([1.0, 2.0]), np.array([2.0, 1.0])])
    assert c.n_effective == float(c.n_raw)
    assert c.method == "unmeasurable"


def test_constant_columns_do_not_fabricate_independence():
    c = effective_trials([np.ones(250), np.ones(250), np.ones(250)])
    assert c.n_effective == float(c.n_raw), "constant columns were treated as measurable"


def test_a_single_trial_is_left_alone():
    assert effective_trials([RNG.normal(size=250)]).n_effective == 1.0


# ---------------------------------------------------------------------- deflation

def test_both_thresholds_are_always_reported():
    """Reporting only the deduplicated threshold would let this module quietly relax every gate
    it touches. The pair makes the size of the correction visible."""
    base = RNG.normal(size=250)
    d = deflation_pair(effective_trials([base.copy() for _ in range(20)]), sd_sharpe=0.30)
    assert {"sr0_raw", "sr0_effective", "n_raw", "n_effective", "threshold_relief"} <= set(d)
    assert d["sr0_effective"] < d["sr0_raw"]
    assert d["threshold_relief"] > 0


def test_gate_authoritative_report_identifies_null_calibration():
    rep = calibrated_census_report(_indep(12, t=80), sd_sharpe=0.30)
    assert rep["method"] == "null_calibrated_participation_ratio"
    assert "independent-null rank" in rep["why"]


def test_deduplication_cannot_raise_a_threshold_or_invent_relief():
    d = deflation_pair(effective_trials(_indep(30)), sd_sharpe=0.30)
    assert d["threshold_relief"] >= -1e-9
    assert d["threshold_relief"] < 0.05, "independent trials got material relief"


def test_expected_max_grows_with_the_trial_count():
    assert expected_max_z(2) < expected_max_z(100) < expected_max_z(10_000)


def test_expected_max_accepts_a_non_integer_effective_count():
    assert expected_max_z(2) <= expected_max_z(7.4) <= expected_max_z(8)


def test_the_real_shape_of_the_problem():
    """2,464 cells at the desk's measured sd(SR). If they behave as far fewer independent
    searches, the DSR bar the nine candidates are failing is the wrong bar."""
    base = [RNG.normal(size=250) for _ in range(40)]
    cols = [b + RNG.normal(size=250) * 0.05 for b in base for _ in range(6)]   # 240 cells, 40 real
    rep = census_report(cols, sd_sharpe=0.30)
    assert rep["n_raw"] == 240
    assert 30 <= rep["n_effective"] <= 60, f"got {rep['n_effective']}"
    assert rep["sr0_effective"] < rep["sr0_raw"]
    assert "both counts are reported" in rep["guard"]
