"""The audit harness must be trustworthy before its numbers are.

Every test here guards a property the audit's conclusions rest on. The harness scores candidates
through the REAL validate(); what it does NOT get to do is quietly diverge from it for speed, or
simulate an alpha that is not the size it claims.
"""
from __future__ import annotations

import numpy as np

from scripts.audit_gate_power import (
    GATES,
    _wilson,
    campaign_stats_fast,
    effective_n_tests,
    score_cohort,
    simulate_cohort,
    simulate_returns,
    summarise,
)
from libs.validation.positive_control import PPY


def test_fast_campaign_path_is_verdict_identical():
    """LOAD-BEARING. campaign_stats_fast skips campaign_pbo_rc, whose classic PBO enumerates
    C(16,8)=12,870 splits and costs ~20x the rest of a replication combined. That is only
    legitimate because the per-candidate path reads cscv and stepdown alone -- legacy_pbo and
    legacy_rc are consumed exclusively by validate()'s legacy branch.

    If that ever stops being true the audit would silently measure a different gauntlet than the
    one it reports on, so the equivalence is asserted on every run rather than trusted."""
    rng = np.random.default_rng(5)
    m, f = simulate_cohort(40, 310, rng, n_true=8, true_ann_sharpe=3.0)
    fast = score_cohort(m, f, fast=True)
    full = score_cohort(m, f, fast=False)
    assert [r["gates"] for r in fast] == [r["gates"] for r in full]
    assert [r["survived"] for r in fast] == [r["survived"] for r in full]


def test_a_simulated_alpha_is_the_size_it_claims():
    """If the generator's realised Sharpe drifted from its target, every power number in the audit
    would be reported against the wrong effect size -- the exact defect R0017 was closed on, where
    a fixed-seed 'true SR +0.5' candidate actually realised -2.32."""
    rng = np.random.default_rng(11)
    target = 3.0
    got = [float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(PPY))
           for r in (simulate_returns(target, 2000, rng) for _ in range(60))]
    # sampling error of an annualised Sharpe over T=2000 daily bars is sqrt(PPY/T) ~= 0.43
    assert abs(float(np.mean(got)) - target) < 0.20
    assert float(np.mean([g > 0 for g in got])) == 1.0


def test_a_null_candidate_carries_no_drift():
    rng = np.random.default_rng(12)
    got = [float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(PPY))
           for r in (simulate_returns(0.0, 2000, rng) for _ in range(60))]
    assert abs(float(np.mean(got))) < 0.20


def test_effective_tests_estimator_has_a_floor_that_is_not_a_finding():
    """THE TRAP THIS AUDIT HAD TO AVOID. When T < N the sample correlation matrix has rank <= T,
    so every eigenvalue-based N_eff reads well below N even on perfectly independent columns.
    Reporting 'only ~180 of 420 tests are independent' from that would be an estimation artifact
    dressed as a finding about the desk's candidates. Only the RATIO to this floor is meaningful."""
    rng = np.random.default_rng(13)
    indep, _ = simulate_cohort(200, 120, rng, n_true=0, true_ann_sharpe=0.0, rho=0.0)
    floor = effective_n_tests(indep)
    assert floor["participation"] < 200.0          # the artifact, on genuinely independent data
    assert floor["participation"] > 60.0           # but not arbitrarily small


def test_correlation_actually_reduces_effective_tests():
    """The estimator must still MOVE with real dependence, or the ratio above measures nothing."""
    rng = np.random.default_rng(14)
    lo, _ = simulate_cohort(120, 400, rng, n_true=0, true_ann_sharpe=0.0, rho=0.0)
    hi, _ = simulate_cohort(120, 400, rng, n_true=0, true_ann_sharpe=0.0, rho=0.8)
    assert effective_n_tests(hi)["participation"] < effective_n_tests(lo)["participation"] / 2


def test_leave_one_out_is_arithmetically_a_relaxation():
    """Dropping a gate can only ADD survivors -- never remove one. A negative delta would mean the
    leave-one-out bookkeeping is wrong, and the marginal-contribution table would be garbage."""
    rng = np.random.default_rng(15)
    m, f = simulate_cohort(60, 310, rng, n_true=15, true_ann_sharpe=5.0)
    s = summarise(score_cohort(m, f))
    for g in GATES:
        assert s["leave_one_out"][g]["delta_fpr"] >= -1e-12
        assert s["leave_one_out"][g]["delta_power"] >= -1e-12


def test_wilson_interval_is_honest_at_the_boundary():
    """The audit lives at 0% and 100%, where the normal approximation returns a zero-width
    interval and would report certainty the data cannot support."""
    lo, hi = _wilson(0, 400)
    assert lo == 0.0 and 0.0 < hi < 0.02          # 0/400 is not proof of impossibility
    lo, hi = _wilson(400, 400)
    assert 0.98 < lo < 1.0 and hi == 1.0
    lo, hi = _wilson(0, 0)
    assert (lo, hi) == (0.0, 1.0)                 # no data means no claim


def test_the_campaign_stats_shim_returns_the_per_candidate_fields():
    rng = np.random.default_rng(16)
    m, _ = simulate_cohort(30, 200, rng, n_true=0, true_ann_sharpe=0.0)
    g = campaign_stats_fast(m)
    assert g.cscv is not None and g.stepdown is not None
    assert g.legacy_pbo is None and g.legacy_rc is None
    assert len(g.stepdown.rejected) == 30
