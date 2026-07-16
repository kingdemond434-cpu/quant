"""Hedge governance, effectiveness, proposals, and lifecycle."""

from __future__ import annotations

from libs.stage14_5.hedging import (
    HedgeLifecycleEngine,
    PortfolioHedgingEngine,
    hedge_effectiveness_score,
    hedge_governance_gate,
)
from libs.stage14_5.models import FactorExposureResult, HedgeType, RegimeExposureResult


def test_governance_approves_only_justified_hedges() -> None:
    # improves CAGR -> approve
    assert hedge_governance_gate(
        expected_cagr_delta=0.01, expected_survival_delta=0.0, expected_tail_reduction=0.0
    ).approved
    # materially improves survival -> approve
    assert hedge_governance_gate(
        expected_cagr_delta=-0.001, expected_survival_delta=0.05, expected_tail_reduction=0.0
    ).approved
    # tail reduction exceeds growth cost -> approve
    assert hedge_governance_gate(
        expected_cagr_delta=-0.01, expected_survival_delta=0.0, expected_tail_reduction=0.05
    ).approved
    # cosmetic vol reduction (no CAGR, no survival, tail<cost) -> REJECT
    rejected = hedge_governance_gate(
        expected_cagr_delta=-0.02, expected_survival_delta=0.0, expected_tail_reduction=0.005
    )
    assert not rejected.approved


def test_hedge_effectiveness_score() -> None:
    eff = hedge_effectiveness_score(
        cagr_contribution=0.3, survival_contribution=0.8, diversification_contribution=0.6,
        tail_risk_contribution=0.7, capacity_impact=0.1,
    )
    assert 0.0 <= eff.hedge_effectiveness_score <= 100.0
    weak = hedge_effectiveness_score(
        cagr_contribution=0.0, survival_contribution=0.0, diversification_contribution=0.0,
        tail_risk_contribution=0.0, capacity_impact=0.9,
    )
    assert weak.hedge_effectiveness_score < eff.hedge_effectiveness_score


def test_hedging_engine_proposes_for_imbalance() -> None:
    eng = PortfolioHedgingEngine(max_family_share=0.4)
    factor = FactorExposureResult(net_usd=0.9, net_directional=0.1, beta=0.2,
                                  volatility_exposure=0.1, factor_exposure_score=90.0,
                                  acceptable=False)
    regime = RegimeExposureResult(by_regime={"crisis": 0.0}, regime_balance_score=20.0,
                                  uncovered_regimes=["crisis"], balanced=False)
    proposals = eng.propose(
        family_weights={"trend": 0.8, "carry": 0.2},  # trend dominates
        factor_result=factor, regime_result=regime, crisis_recommended=True,
    )
    types = {p.hedge_type for p in proposals}
    assert HedgeType.ALPHA in types
    assert HedgeType.FACTOR in types
    assert HedgeType.REGIME in types
    assert HedgeType.CRISIS in types


def test_hedging_engine_quiet_when_balanced() -> None:
    eng = PortfolioHedgingEngine(max_family_share=0.6)
    proposals = eng.propose(family_weights={"trend": 0.5, "carry": 0.5})
    assert proposals == []


def test_propose_governed_filters_unjustified() -> None:
    eng = PortfolioHedgingEngine()
    governed = eng.propose_governed(family_weights={"trend": 0.9, "carry": 0.1})
    # the alpha rebalance improves survival/tail, so it survives governance
    assert all(
        hedge_governance_gate(
            expected_cagr_delta=p.expected_cagr_delta,
            expected_survival_delta=p.expected_survival_delta,
            expected_tail_reduction=p.expected_tail_reduction,
        ).approved
        for p in governed
    )


def test_lifecycle_closes_spent_hedges() -> None:
    eng = HedgeLifecycleEngine(min_effectiveness=40.0)
    keep = eng.evaluate(HedgeType.ALPHA, crisis_active=True, effectiveness_score=80.0,
                        survival_benefit=0.05, cost=0.01, benefit=0.1)
    assert not keep.close
    # crisis hedge after the crisis ends
    ended = eng.evaluate(HedgeType.CRISIS, crisis_active=False, effectiveness_score=80.0,
                         survival_benefit=0.05, cost=0.01, benefit=0.1)
    assert ended.close
    assert "crisis regime ended" in ended.reasons
    # cost exceeds benefit
    costly = eng.evaluate(HedgeType.FACTOR, crisis_active=True, effectiveness_score=80.0,
                          survival_benefit=0.05, cost=0.2, benefit=0.1)
    assert costly.close
