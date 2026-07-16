"""Cross-campaign multiple-testing control (committee T3)."""

from __future__ import annotations

from libs.autodiscovery.models import CandidateStatus, Family, Hypothesis, ValidationMetrics
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.store.connection import Database
from libs.validation.economic_prior import MechanismType


def _hyp(i: int) -> Hypothesis:
    return Hypothesis(
        family=Family.TREND, subtype=f"variant_{i}", symbol="EURUSD",
        params={"fast": float(i)}, mechanism=MechanismType.RISK_PREMIUM,
        edge_source="test", failure_modes=["test"],
    )


def test_effective_trials_accumulates_across_campaigns(db: Database) -> None:
    lab = AutoDiscoveryLab(db, lambda _s: None)
    assert lab._effective_trials(3) == 3  # empty ledger -> only this cycle's trials

    for i in range(5):  # simulate 5 trials recorded in prior campaigns
        lab.store.record(
            campaign_id="prior", hyp=_hyp(i), status=CandidateStatus.REJECTED,
            metrics=ValidationMetrics(), survived=False, rejection_reason="failed: dsr",
        )

    # A new cycle of 3 trials is deflated against 5 + 3 = 8 cumulative trials, not just 3.
    assert lab._effective_trials(3) == 8
