"""Prioritization, Data Opportunity Engine, and Research ROI Monitor."""

from __future__ import annotations

from tests.autodiscovery.conftest import noise_provider

from libs.autodiscovery.data_opportunity import DataOpportunityEngine
from libs.autodiscovery.generators import planned_hypotheses
from libs.autodiscovery.models import CandidateStatus, Family, ValidationMetrics
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.autodiscovery.prioritization import family_rank, prioritize
from libs.autodiscovery.research_roi import ResearchROIMonitor
from libs.data.timeframe import Timeframe
from libs.store.connection import Database


def test_prioritization_orders_durable_families_first() -> None:
    plan = prioritize(planned_hypotheses(["EURUSD"]))
    first_family = plan[0][0].family
    # carry/risk-premia/cross-asset/regime/liquidity outrank trend/momentum/etc.
    assert family_rank(first_family) <= family_rank(Family.TREND)
    assert family_rank(Family.CARRY) < family_rank(Family.MOMENTUM)
    # every planned hypothesis is still present (ordering only, nothing dropped)
    assert len(plan) == len(planned_hypotheses(["EURUSD"]))


def test_data_opportunity_ranks_by_roi() -> None:
    report = DataOpportunityEngine().report()
    scores = [row["roi_score"] for row in report.ranked]
    assert scores == sorted(scores, reverse=True)        # descending ROI
    assert report.top_recommendation                      # a concrete next dataset
    # the dataset that unlocks the highest-priority family (carry) should rank well
    names = [row["name"] for row in report.ranked[:4]]
    assert "funding_rates" in names or "yield_curves" in names


def test_research_roi_monitor_on_zero_survivors(db: Database) -> None:
    lab = AutoDiscoveryLab(db, noise_provider(), bar=Timeframe.D1)
    lab.cycle(["EURUSD"])
    report = ResearchROIMonitor(lab.store).report()
    assert report.total_tested > 0
    assert report.total_survivors == 0          # noise -> zero (honest)
    assert report.survivor_rate == 0.0
    assert report.by_family                       # per-family yield computed
    assert len(report.recommended_focus) >= 1


def test_research_roi_empty_store(db: Database) -> None:
    report = ResearchROIMonitor(CandidateStoreFactory(db)).report()
    assert report.total_tested == 0
    assert report.validation_pass_rate == 0.0


def CandidateStoreFactory(db: Database):
    from libs.autodiscovery.memory import CandidateStore
    return CandidateStore(db)


def test_family_yield_fields(db: Database) -> None:
    from libs.autodiscovery.memory import CandidateStore
    from libs.autodiscovery.models import Hypothesis
    from libs.validation.economic_prior import MechanismType
    store = CandidateStore(db)
    hyp = Hypothesis(family=Family.CARRY, subtype="drift_proxy", symbol="EURUSD",
                     params={"lookback": 200.0}, mechanism=MechanismType.RISK_PREMIUM,
                     edge_source="carry", failure_modes=["proxy"])
    store.record(campaign_id="c1", hyp=hyp, status=CandidateStatus.REJECTED,
                 metrics=ValidationMetrics(), survived=False, rejection_reason="failed: dsr")
    report = ResearchROIMonitor(store).report()
    carry = next(f for f in report.by_family if f.family == "carry")
    assert carry.tested == 1
    assert carry.rejected == 1
    assert carry.survivors == 0
