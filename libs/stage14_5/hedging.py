"""Portfolio hedging engine — institutional protection, governed and lifecycle-managed.

Proposes diversifying tilts and crisis-alpha adds (never retail offsets). A hedge may exist ONLY
if it improves expected CAGR, materially improves survival, or its tail-risk reduction exceeds any
growth it costs — otherwise it is rejected. The lifecycle engine closes hedges that have served
their purpose. Survival dominates return; growth dominates cosmetic smoothness.
"""

from __future__ import annotations

from collections.abc import Mapping

from libs.stage14_5.models import (
    FactorExposureResult,
    HedgeEffectiveness,
    HedgeGovernanceVerdict,
    HedgeLifecycleDecision,
    HedgeProposal,
    HedgeType,
    RegimeExposureResult,
)

_EFFECTIVENESS_WEIGHTS: dict[str, float] = {
    "cagr": 0.25,
    "survival": 0.35,
    "diversification": 0.20,
    "tail": 0.20,
}


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def hedge_governance_gate(
    *,
    expected_cagr_delta: float,
    expected_survival_delta: float,
    expected_tail_reduction: float,
    survival_materiality: float = 0.02,
) -> HedgeGovernanceVerdict:
    """A hedge is approved only if it earns its place; never to smooth volatility cosmetically."""
    growth_cost = max(0.0, -expected_cagr_delta)
    if expected_cagr_delta > 0:
        return HedgeGovernanceVerdict(approved=True, reason="improves expected CAGR")
    if expected_survival_delta >= survival_materiality:
        return HedgeGovernanceVerdict(approved=True, reason="materially improves survival")
    if expected_tail_reduction > growth_cost:
        return HedgeGovernanceVerdict(
            approved=True, reason="tail-risk reduction exceeds growth reduction"
        )
    return HedgeGovernanceVerdict(
        approved=False, reason="rejected: sacrifices growth without survival/tail justification"
    )


def hedge_effectiveness_score(
    *,
    cagr_contribution: float,
    survival_contribution: float,
    diversification_contribution: float,
    tail_risk_contribution: float,
    capacity_impact: float,
) -> HedgeEffectiveness:
    positive = (
        _EFFECTIVENESS_WEIGHTS["cagr"] * _clip01(cagr_contribution)
        + _EFFECTIVENESS_WEIGHTS["survival"] * _clip01(survival_contribution)
        + _EFFECTIVENESS_WEIGHTS["diversification"] * _clip01(diversification_contribution)
        + _EFFECTIVENESS_WEIGHTS["tail"] * _clip01(tail_risk_contribution)
    )
    score = 100.0 * _clip01(positive - 0.2 * _clip01(capacity_impact))
    return HedgeEffectiveness(
        hedge_effectiveness_score=score, cagr_contribution=cagr_contribution,
        survival_contribution=survival_contribution,
        diversification_contribution=diversification_contribution,
        tail_risk_contribution=tail_risk_contribution, capacity_impact=capacity_impact,
    )


class PortfolioHedgingEngine:
    """Proposes institutional hedges from concentration / factor / regime / crisis signals."""

    def __init__(self, *, max_family_share: float = 0.40) -> None:
        self.max_family_share = max_family_share

    def propose(
        self,
        *,
        family_weights: Mapping[str, float],
        factor_result: FactorExposureResult | None = None,
        regime_result: RegimeExposureResult | None = None,
        crisis_recommended: bool = False,
    ) -> list[HedgeProposal]:
        proposals: list[HedgeProposal] = []
        proposals.extend(self._alpha_hedges(family_weights))
        if factor_result is not None and not factor_result.acceptable:
            proposals.append(
                HedgeProposal(
                    hedge_type=HedgeType.FACTOR, target="dominant_factor",
                    rationale="reduce concentrated factor exposure",
                    expected_cagr_delta=-0.002, expected_survival_delta=0.03,
                    expected_tail_reduction=0.05,
                )
            )
        if regime_result is not None:
            for regime in regime_result.uncovered_regimes:
                proposals.append(
                    HedgeProposal(
                        hedge_type=HedgeType.REGIME, target=regime,
                        rationale=f"add exposure to uncovered regime: {regime}",
                        expected_cagr_delta=0.001, expected_survival_delta=0.02,
                        expected_tail_reduction=0.02,
                    )
                )
        if crisis_recommended:
            proposals.append(
                HedgeProposal(
                    hedge_type=HedgeType.CRISIS, target="crisis_alpha",
                    rationale="add crisis-alpha exposure (pays during breakdowns)",
                    expected_cagr_delta=-0.005, expected_survival_delta=0.06,
                    expected_tail_reduction=0.10,
                )
            )
        return proposals

    def propose_governed(self, **kwargs: object) -> list[HedgeProposal]:
        """Propose hedges and keep only those that pass governance."""
        return [
            p
            for p in self.propose(**kwargs)  # type: ignore[arg-type]
            if hedge_governance_gate(
                expected_cagr_delta=p.expected_cagr_delta,
                expected_survival_delta=p.expected_survival_delta,
                expected_tail_reduction=p.expected_tail_reduction,
            ).approved
        ]

    def _alpha_hedges(self, family_weights: Mapping[str, float]) -> list[HedgeProposal]:
        total = sum(abs(v) for v in family_weights.values())
        if total <= 0 or len(family_weights) < 2:
            return []
        shares = {k: abs(v) / total for k, v in family_weights.items()}
        dominant, top_share = max(shares.items(), key=lambda kv: kv[1])
        if top_share <= self.max_family_share:
            return []
        weakest = min(shares.items(), key=lambda kv: kv[1])[0]
        return [
            HedgeProposal(
                hedge_type=HedgeType.ALPHA, target=weakest,
                rationale=f"{dominant} dominates ({top_share:.0%}); rebalance toward {weakest}",
                expected_cagr_delta=0.0, expected_survival_delta=0.03,
                expected_tail_reduction=0.04,
            )
        ]


class HedgeLifecycleEngine:
    """Closes hedges that have outlived their purpose (fail-closed toward closing)."""

    def __init__(self, *, min_effectiveness: float = 40.0) -> None:
        self.min_effectiveness = min_effectiveness

    def evaluate(
        self,
        hedge_type: HedgeType,
        *,
        crisis_active: bool,
        effectiveness_score: float,
        survival_benefit: float,
        cost: float,
        benefit: float,
    ) -> HedgeLifecycleDecision:
        reasons: list[str] = []
        if hedge_type is HedgeType.CRISIS and not crisis_active:
            reasons.append("crisis regime ended")
        if effectiveness_score < self.min_effectiveness:
            reasons.append("hedge effectiveness fell below threshold")
        if survival_benefit <= 0.0:
            reasons.append("portfolio survival benefit disappeared")
        if cost > benefit:
            reasons.append("hedge cost exceeds benefit")
        return HedgeLifecycleDecision(close=bool(reasons), reasons=reasons)
