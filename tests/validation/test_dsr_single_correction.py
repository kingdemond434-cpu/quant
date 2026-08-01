"""The multiplicity penalty is paid ONCE. Pinned, because it is easy to 'restore' by accident.

DSR is a Probabilistic Sharpe Ratio against a DEFLATED benchmark, and that deflation is a
multiplicity correction over the campaign. On the per-candidate path Romano-Wolf already controls
family-wise error over the SAME N candidates, so deflating again corrected twice and compounded
two family-wise bars into one nothing could pass.

A future reader seeing `n_trials=1` will be tempted to call it a bug and 'fix' it. These tests
are the reason not to: the second correction was measured to buy zero error control and cost up
to 78 points of power.
"""
from __future__ import annotations

import numpy as np
from scripts.audit_gate_power import GATES, score_cohort, simulate_cohort

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="test", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="simulated",
    failure_modes=["simulated -- never tradeable"],
)


def _cohort(seed=3, n=120, t=310, n_true=20, sr=5.0):
    rng = np.random.default_rng(seed)
    return simulate_cohort(n, t, rng, n_true=n_true, true_ann_sharpe=sr)


def test_the_per_candidate_path_does_not_deflate_and_the_legacy_path_does():
    """The whole change, asserted at the boundary that selects between the two paths.

    Same candidate, same cohort: with a campaign supplied Romano-Wolf carries the multiplicity so
    DSR must not deflate; without one, nothing else corrects, so it must."""
    m, flags = _cohort()
    gates = campaign_gate_stats(m)
    assert gates is not None
    sh = np.array([sharpe_ratio(m[:, i]) for i in range(m.shape[1])])
    common = {"hypothesis": _HYP, "n_trials": m.shape[1], "sharpe_estimates": sh,
              "returns_matrix": m}
    col = int(np.argmax(flags))               # a genuine alpha

    per = validate(m[:, col], campaign=gates, column=col, **common)
    legacy = validate(m[:, col], pbo=gates.legacy_pbo, rc=gates.legacy_rc, **common)
    # the undeflated PSR is strictly larger than the deflated DSR on the same returns
    assert per.metrics.dsr > legacy.metrics.dsr
    assert per.gates["dsr"] is True and legacy.gates["dsr"] is False


def test_removing_the_duplicate_correction_recovers_power():
    """REGRESSION PIN on the measured gain. Before the change the full stack admitted 5.8% of
    genuine SR=5 alphas; the audit showed dropping DSR's deflation entirely reaches 83.8%. This
    asserts the recovery is real and large, without pinning a brittle exact figure."""
    m, flags = _cohort(seed=11, n=200, sr=5.0)
    rows = score_cohort(m, flags)
    trues = [r for r in rows if r["is_true"]]
    power = sum(r["survived"] for r in trues) / len(trues)
    assert power > 0.35, f"power collapsed to {power:.1%} -- the duplicate deflation is back"


def test_false_positive_control_survives_the_change():
    """The change is only legitimate if Romano-Wolf alone still holds the line. A cohort of pure
    nulls must still be rejected essentially always -- this is the half that must NOT move."""
    rng = np.random.default_rng(29)
    m, flags = simulate_cohort(200, 310, rng, n_true=0, true_ann_sharpe=0.0)
    rows = score_cohort(m, flags)
    fpr = sum(r["survived"] for r in rows) / len(rows)
    assert fpr <= 0.01, f"false positives at {fpr:.2%} -- error control was lost, not relocated"


def test_the_moment_aware_half_is_retained():
    """Only the DEFLATION was removed. PSR still runs, so DSR remains a real gate rather than a
    constant True -- otherwise a candidate with a negative Sharpe would sail through it."""
    rng = np.random.default_rng(31)
    m, _flags = simulate_cohort(60, 310, rng, n_true=0, true_ann_sharpe=0.0)
    gates = campaign_gate_stats(m)
    assert gates is not None
    sh = np.array([sharpe_ratio(m[:, i]) for i in range(m.shape[1])])
    worst = int(np.argmin(sh))
    v = validate(m[:, worst], hypothesis=_HYP, n_trials=m.shape[1], sharpe_estimates=sh,
                 returns_matrix=m, campaign=gates, column=worst)
    assert v.gates["dsr"] is False, "DSR became a rubber stamp -- it must still reject a loser"


def test_every_other_gate_is_untouched():
    """Blast radius. Exactly one gate's input changed; the rest of the stack must be identical,
    or this commit is a broader relaxation than it claims to be."""
    m, flags = _cohort(seed=5, n=80, sr=5.0)
    rows = score_cohort(m, flags)
    assert set(rows[0]["gates"]) == set(GATES)
    # the economic gates still reject a meaningful share of pure noise
    rng = np.random.default_rng(7)
    mn, fn = simulate_cohort(80, 310, rng, n_true=0, true_ann_sharpe=0.0)
    nulls = score_cohort(mn, fn)
    for g in ("expected_value", "cpcv", "walk_forward"):
        passes = sum(r["gates"][g] for r in nulls) / len(nulls)
        assert 0.2 < passes < 0.8, f"{g} passes {passes:.0%} of nulls -- it stopped discriminating"
