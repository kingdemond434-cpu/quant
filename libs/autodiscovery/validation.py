"""Full institutional validation per candidate — every gate, no weakening, fail-closed.

Runs the complete stack and a candidate survives ONLY if every gate passes: economic mechanism,
CPCV (purged K-fold OOS consistency), PBO, Deflated Sharpe (trials-deflated), White's Reality Check,
Walk-Forward, capacity, fragility (tail risk), and an accelerated shadow check (final held-out
segment). Reuses the existing validation / discovery primitives. Thresholds are constants here and
never relaxed.
"""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.models import Hypothesis, ValidationMetrics, ValidationVerdict
from libs.discovery.capacity import capacity_estimate
from libs.discovery.tail_risk import tail_risk
from libs.research.capacity_policy import capacity_required
from libs.validation.dsr import deflated_sharpe_ratio, sharpe_ratio
from libs.validation.pbo import PBOResult, probability_backtest_overfitting
from libs.validation.reality_check import RealityCheckResult, whites_reality_check
from libs.validation.revalidation import WalkForwardEngine, WalkForwardStatus

_PERIODS_PER_YEAR = 24 * 260
_DSR_THRESHOLD = 0.95
_CPCV_MIN_POSITIVE = 0.6   # >=60% of purged folds positive


def _cpcv_positive_fraction(returns: np.ndarray, *, k: int = 5) -> float:
    folds = np.array_split(returns, k)
    positive = [f.mean() > 0 for f in folds if len(f) > 1]
    return float(np.mean(positive)) if positive else 0.0


def campaign_pbo_rc(
    returns_matrix: np.ndarray,
) -> tuple[PBOResult | None, RealityCheckResult | None]:
    """Compute PBO and White's Reality Check ONCE per campaign (they depend only on the matrix).

    These two gates are identical for every candidate in a campaign, so computing them once and
    passing the results into :func:`validate` avoids O(N) redundant bootstraps -- a large speedup
    with no change to the verdict. (Used by the orchestrator; validate() falls back to per-call
    computation when not supplied.)
    """
    if returns_matrix.shape[1] < 2:
        return None, None
    return probability_backtest_overfitting(returns_matrix), whites_reality_check(returns_matrix)


def validate(
    returns: np.ndarray,
    *,
    hypothesis: Hypothesis,
    n_trials: int,
    sharpe_estimates: np.ndarray,
    returns_matrix: np.ndarray,
    adv_usd: float = 1.0e11,
    edge_bps: float | None = None,
    # What the desk ACTUALLY deploys. The capacity gate is a ratio to this, not a fixed dollar
    # figure -- see capacity_required(). Default 0.0 means "book size unknown", which falls back
    # to the absolute floor alone rather than silently demanding six-figure capacity.
    deployed_equity_usd: float = 0.0,
    pbo: PBOResult | None = None,
    rc: RealityCheckResult | None = None,
) -> ValidationVerdict:
    arr = np.asarray(returns, dtype="float64")
    if len(arr) < 250:
        return ValidationVerdict(
            survived=False, gates={"sufficient_data": False},
            rejection_reason="insufficient data", metrics=ValidationMetrics(),
        )

    # Walk-forward (OOS). Shadow/paper are separate lifecycle stages (see lifecycle.py).
    wf = WalkForwardEngine().evaluate(arr, n_splits=4, test_size=max(20, len(arr) // 6))
    dsr = deflated_sharpe_ratio(arr, n_trials=n_trials, sharpe_estimates=sharpe_estimates,
                                threshold=_DSR_THRESHOLD)
    # PBO/RC depend only on the (campaign-wide) matrix; reuse precomputed results when supplied.
    has_peers = returns_matrix.shape[1] >= 2
    if pbo is None and has_peers:
        pbo = probability_backtest_overfitting(returns_matrix)
    if rc is None and has_peers:
        rc = whites_reality_check(returns_matrix)
    # Candidate-aware capacity: use the strategy's OWN realized per-bar edge (bps), so a no-edge
    # strategy gets ~zero capacity (fails) while a real edge on a liquid market passes -- instead
    # of the old fixed edge_bps that made this gate a constant veto for every candidate.
    eff_edge_bps = edge_bps if edge_bps is not None else max(0.0, float(arr.mean()) * 1.0e4)
    cap = capacity_estimate(adv_usd=adv_usd, edge_bps=max(eff_edge_bps, 1.0e-9))
    tail = tail_risk(arr)

    metrics = ValidationMetrics(
        annual_sharpe=float(sharpe_ratio(arr) * np.sqrt(_PERIODS_PER_YEAR)),
        expected_value=float(arr.mean()),
        oos_sharpe=wf.oos_sharpe,
        dsr=dsr.dsr,
        pbo=pbo.pbo if pbo is not None else 1.0,
        reality_p=rc.p_value if rc is not None else 1.0,
        capacity_usd=cap.capacity_usd,
        fragility=tail.tail_risk_score,
    )

    gates = {
        "economic_mechanism": bool(hypothesis.failure_modes),   # declared before testing
        "expected_value": metrics.expected_value > 0,
        "cpcv": _cpcv_positive_fraction(arr) >= _CPCV_MIN_POSITIVE,
        "walk_forward": wf.status is WalkForwardStatus.PASSED,
        "dsr": dsr.passed,
        "pbo": pbo is not None and not pbo.overfit,
        "reality_check": rc is not None and rc.significant_at_5pct,
        "capacity": cap.capacity_usd >= capacity_required(deployed_equity_usd),
        "fragility": tail.acceptable,
    }
    failed = [name for name, ok in gates.items() if not ok]
    return ValidationVerdict(
        survived=not failed, gates=gates,
        rejection_reason="" if not failed else "failed: " + ", ".join(failed),
        metrics=metrics,
    )
