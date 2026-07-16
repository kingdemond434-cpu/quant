"""Improvement controller — the Stage 13 master coordinator.

Receives health/decay signals, produces an :class:`ImprovementPlan` of *recommendations*, and
journals them. Governance is structural: the controller has no method that writes production
weights. ``apply_weight_proposal`` defers to the Portfolio Engine (risk overrides alpha); Stage
13 may recommend and schedule but may not directly change production portfolio weights.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.alpha.card import AlphaCard, LiveMetrics
from libs.portfolio.engine import PortfolioEngine
from libs.portfolio.models import AlphaInput, PortfolioTarget
from libs.self_improvement.audit import ImprovementAudit
from libs.self_improvement.capital_reallocator import CapitalReallocator
from libs.self_improvement.decay_engine import AlphaDecayEngine
from libs.self_improvement.errors import GovernanceError
from libs.self_improvement.health_monitor import AlphaHealthMonitor
from libs.self_improvement.models import (
    DecayAssessment,
    DecayLevel,
    ImprovementAction,
    ImprovementActionType,
    ImprovementPlan,
    ResearchPriority,
    WeightProposal,
)
from libs.self_improvement.weight_optimizer import DynamicWeightOptimizer, WeightCandidate


class ImprovementController:
    """Coordinates the self-improvement engines into a recommendation plan."""

    def __init__(
        self,
        *,
        health_monitor: AlphaHealthMonitor | None = None,
        decay_engine: AlphaDecayEngine | None = None,
        weight_optimizer: DynamicWeightOptimizer | None = None,
        capital_reallocator: CapitalReallocator | None = None,
        audit: ImprovementAudit | None = None,
    ) -> None:
        self.health_monitor = health_monitor or AlphaHealthMonitor()
        self.decay_engine = decay_engine or AlphaDecayEngine()
        self.weight_optimizer = weight_optimizer or DynamicWeightOptimizer()
        self.capital_reallocator = capital_reallocator or CapitalReallocator()
        self.audit = audit

    def evaluate(
        self,
        observations: Sequence[tuple[AlphaCard, LiveMetrics]],
        *,
        current_weights: Mapping[str, float] | None = None,
        total_capital: float = 0.0,
        regime_match: Mapping[str, float] | None = None,
        research_priorities: Sequence[ResearchPriority] | None = None,
    ) -> ImprovementPlan:
        """Produce a recommendation plan from current alpha health and decay."""
        actions: list[ImprovementAction] = []
        candidates: list[WeightCandidate] = []

        for card, live in observations:
            health = self.health_monitor.assess(card, live)
            decay = self.decay_engine.assess(card, live)
            match = regime_match.get(card.id, 1.0) if regime_match else 1.0
            candidates.append(
                WeightCandidate(
                    alpha_id=card.id,
                    health_score=health.health_score,
                    decay_multiplier=decay.weight_multiplier,
                    regime_match=match,
                )
            )
            actions.extend(self._decay_actions(card.id, decay))

        proposal = self.weight_optimizer.propose(candidates)
        if current_weights is not None:
            actions.extend(
                self.capital_reallocator.propose(
                    current_weights, proposal.weights, total_capital=total_capital
                )
            )

        plan = ImprovementPlan(
            actions=actions,
            weight_proposal=proposal,
            research_priorities=list(research_priorities or []),
        )
        if self.audit is not None:
            self.audit.record_plan(plan)
        return plan

    @staticmethod
    def _decay_actions(alpha_id: str, decay: DecayAssessment) -> list[ImprovementAction]:
        if decay.decay_level is DecayLevel.DEAD:
            return [
                ImprovementAction(
                    type=ImprovementActionType.RETIRE, target_id=alpha_id,
                    rationale="decay level DEAD -> retire",
                    detail={"decay_score": decay.decay_score}, requires_portfolio_approval=True,
                )
            ]
        if decay.decay_level is DecayLevel.DECAYING:
            return [
                ImprovementAction(
                    type=ImprovementActionType.PAUSE, target_id=alpha_id,
                    rationale="decaying -> pause capital increases",
                    detail={"allow_increase": False}, requires_portfolio_approval=True,
                )
            ]
        if decay.decay_level in (DecayLevel.WATCH, DecayLevel.WEAK):
            return [
                ImprovementAction(
                    type=ImprovementActionType.WEIGHT_CHANGE, target_id=alpha_id,
                    rationale=decay.recommended_action,
                    detail={"weight_multiplier": decay.weight_multiplier},
                    requires_portfolio_approval=True,
                )
            ]
        return []

    def apply_weight_proposal(
        self,
        proposal: WeightProposal,
        portfolio_engine: PortfolioEngine,
        alphas: Sequence[AlphaInput],
        *,
        correlation: np.ndarray | None = None,
        method: str = "optimize",
    ) -> PortfolioTarget:
        """Realize a weight proposal — ONLY through the Portfolio Engine (the approver).

        Stage 13 cannot set production weights. The Portfolio Engine re-derives the constrained
        target (risk overrides alpha); the proposal is advisory input only.
        """
        if not proposal.requires_portfolio_approval:
            raise GovernanceError("weight proposals must require Portfolio Engine approval")
        return portfolio_engine.build_portfolio(
            alphas, correlation=correlation, method=method
        )
