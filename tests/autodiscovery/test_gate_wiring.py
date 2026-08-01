"""The 2026-08-01 wiring of the robustness filters into the gauntlet, and the UNMEASURED state.

WHY THIS FILE EXISTS. An audit on 2026-08-01 walked the production import graph for every
transcript-derived module and found libs/validation/robustness_filters.py imported by exactly one
file: its own test. 165 lines of measured, correct filtering that reached no candidate the desk
ever screened. `beats_baselines` is the same failure one step further along -- it was wired, but
its input was never supplied, so it returned True for every candidate for months and read as a
passed gate in every artifact.

Both failures are invisible in a green test suite. These tests make them visible instead.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import validate
from libs.validation.economic_prior import MechanismType
from libs.validation.revalidation import WalkForwardEngine

_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="wiring", symbol="X", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="test fixture",
    failure_modes=["decays when the crowd arrives"],
)


def _cohort(seed: int = 0, t: int = 600, n: int = 6) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0004, 0.01, (t, n))


def _run(m: np.ndarray, **kw):
    sh = np.array([m[:, i].mean() / m[:, i].std() for i in range(m.shape[1])])
    return validate(m[:, 0], hypothesis=_HYP, n_trials=m.shape[1], sharpe_estimates=sh,
                    returns_matrix=m, **kw)


# ------------------------------------------------------------------ the filters actually run

def test_the_luck_filter_is_a_real_gate_not_a_dead_import():
    """The audit's finding in one assertion: robustness_filters must be reachable from a
    candidate's verdict, not merely from its own test file."""
    assert "not_too_lucky" in _run(_cohort()).gates


def test_sample_adequacy_runs_when_the_trade_count_is_supplied():
    v = _run(_cohort(), n_trades=9)
    assert v.gates["sample_adequacy"] is False, "9 trades is below the 30 minimum"
    assert _run(_cohort(), n_trades=500).gates["sample_adequacy"] is True


def test_a_thin_trade_count_can_actually_sink_a_candidate():
    """The hole this plugs: every statistic in the gauntlet is per-OBSERVATION, so a 5,000-bar
    series holding one position the whole time has 5,000 observations and one bet. Without this
    gate nothing in validate() could tell the difference."""
    v = _run(_cohort(seed=3), n_trades=2)
    assert not v.survived
    assert "sample_adequacy" in v.rejection_reason


# ------------------------------------------------------ UNMEASURED is not PASSED

def test_a_gate_with_no_input_is_reported_unmeasured_never_passed():
    """The `beats_baselines` lesson, encoded. That gate returned True for every candidate this
    desk ever screened because no caller supplied benchmark_returns, and read green throughout.
    An input nobody supplied means nobody looked, and the verdict has to say so."""
    v = _run(_cohort())
    assert "sample_adequacy" in v.unmeasured
    assert "beats_baselines" in v.unmeasured
    assert "UNMEASURED" in v.rejection_reason


def test_supplying_the_input_moves_a_gate_out_of_unmeasured():
    assert "sample_adequacy" not in _run(_cohort(), n_trades=100).unmeasured


def test_unmeasured_does_not_silently_block_a_candidate():
    """Deliberate. This is a SCREEN with zero promotion authority, and failing candidates for an
    input their caller does not have would kill real alphas -- the one place where unknown must
    escalate rather than block. Loud, not fatal."""
    m = _cohort(seed=7)
    a, b = _run(m), _run(m, n_trades=500)
    assert a.unmeasured and not [u for u in b.unmeasured if u == "sample_adequacy"]
    # The only difference between these two runs is an input, so survival must not flip on it
    # unless the gate it feeds actually failed.
    assert a.survived == b.survived


def test_every_unmeasured_name_is_a_gate_someone_could_actually_supply():
    v = _run(_cohort())
    for name in v.unmeasured:
        assert name in ("sample_adequacy", "beats_baselines"), f"unknown unmeasured gate {name}"


# ------------------------------------------------------------- the walk-forward IS statistics

def test_walk_forward_now_reports_the_in_sample_side_it_used_to_discard():
    """The engine was already splitting train/test and computing statistics on the test side
    only. Without the train side, the most diagnostic comparison in backtesting -- how much worse
    did it get out of sample, and is that gap bigger than sampling noise -- was uncomputable by
    any caller."""
    rng = np.random.default_rng(11)
    r = rng.normal(0.0006, 0.012, 800)
    wf = WalkForwardEngine().evaluate(r, n_splits=4, test_size=120)
    assert wf.n_is > 0 and wf.n_oos > 0
    assert np.isfinite(wf.is_sharpe)


def test_in_sample_beats_out_of_sample_on_a_deliberately_overfitted_series():
    """A series engineered so the early data is strong and the late data is noise. IS Sharpe must
    exceed OOS Sharpe, or the two are not measuring what their names say."""
    rng = np.random.default_rng(12)
    strong = rng.normal(0.004, 0.01, 600)
    noise = rng.normal(0.0, 0.01, 200)
    wf = WalkForwardEngine().evaluate(np.concatenate([strong, noise]), n_splits=4, test_size=50)
    assert wf.is_sharpe > wf.oos_sharpe


def test_a_report_built_without_the_new_fields_still_passes_the_luck_filter():
    """Backwards compatibility with intent. is_sharpe defaults to 0.0, and not_too_lucky treats a
    non-positive IS Sharpe as 'nothing to compare' and passes -- it must never invent a verdict
    from a default."""
    from libs.validation.robustness_filters import not_too_lucky
    assert not_too_lucky(0.0, 0.0, 0, 0).passed


# ------------------------------------------------------------------------------ no regression

def test_wiring_did_not_change_the_verdict_of_an_existing_caller():
    """Every pre-existing call site omits n_trades and benchmark_returns. Their candidates must
    survive or fail exactly as before -- the new gates add information, they do not move the bar
    for callers that cannot feed them."""
    m = _cohort(seed=21)
    v = _run(m)
    prior = {k: val for k, val in v.gates.items() if k != "not_too_lucky"}
    assert "sample_adequacy" not in prior, "an unsupplied gate must not appear in gates at all"
    assert v.survived == (not [g for g in v.gates.values() if not g])


@pytest.mark.parametrize("n_trades", [0, 1, 29, 30, 31, 10_000])
def test_sample_adequacy_boundary_is_where_the_constant_says(n_trades: int):
    from libs.validation.robustness_filters import MIN_TRADES
    assert _run(_cohort(), n_trades=n_trades).gates["sample_adequacy"] is (n_trades >= MIN_TRADES)
