"""``libs.stage14`` — institutional portfolio construction & compounding engine.

Transforms approved Stage 13.5 ``SignalPackage`` objects into capital allocations optimized for
long-term compounded wealth: geometric-growth and survival first, fractional-Kelly sizing, risk
budgeting at the sleeve level, dynamic leverage, a portfolio state machine, capacity ENFORCEMENT,
and fail-closed governance + portfolio kill criteria. Survival dominates return.

Reuses Architecture v1.0: ``libs.risk`` (Kelly/drawdown), ``libs.discovery`` (Monte-Carlo survival,
stress scenarios, log-growth), ``libs.validation`` (walk-forward governance), ``libs.portfolio``
(weight-construction substrate), and the immutable ``libs.store`` audit log. No duplicate
abstractions; the orchestrator is ``PortfolioConstructionEngine`` (distinct from
``libs.portfolio.PortfolioEngine``).
"""

from __future__ import annotations

from libs.stage14.allocation import (
    AdaptiveReinvestmentEngine,
    DrawdownAwareAllocator,
    DynamicLeverageEngine,
    PortfolioRiskBudgetEngine,
    SleeveAllocator,
    group_by_sleeve,
)
from libs.stage14.analytics import (
    CapitalEfficiencyEngine,
    MarginalContributionEngine,
    PortfolioConvexityEngine,
    PortfolioCorrelationEngine,
    PortfolioResilienceEngine,
    PortfolioStressEngine,
    PortfolioSurvivalEngine,
)
from libs.stage14.attribution import PortfolioAttribution, PortfolioAttributionEngine
from libs.stage14.audit import PortfolioAudit
from libs.stage14.capacity import PortfolioCapacityEngine, PortfolioCapacityGovernor
from libs.stage14.engine import PortfolioConstructionEngine
from libs.stage14.errors import PortfolioGovernanceError, Stage14Error
from libs.stage14.governance import PortfolioKillCriteria, portfolio_governance_gate
from libs.stage14.growth import CapitalGrowthSimulator, GeometricGrowthEngine
from libs.stage14.kelly import FractionalKellyEngine, KellyEngine, KellyEstimate
from libs.stage14.models import (
    AlphaSleeve,
    CapacityGovernorAction,
    ConvexityResult,
    CorrelationResult,
    EfficiencyResult,
    GeometricGrowthResult,
    GrowthSimResult,
    InstitutionalPortfolioScore,
    KillDecision,
    LeverageDecision,
    MarginalContribution,
    PortfolioCapacityResult,
    PortfolioConstructionResult,
    PortfolioPackage,
    PortfolioState,
    ReinvestmentDecision,
    ResilienceResult,
    RiskBudget,
    StressResult,
    SurvivalResult,
)
from libs.stage14.score import institutional_portfolio_score
from libs.stage14.state_machine import PortfolioStateMachine

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "AlphaSleeve",
    "PortfolioState",
    "RiskBudget",
    "GeometricGrowthResult",
    "GrowthSimResult",
    "SurvivalResult",
    "PortfolioCapacityResult",
    "CapacityGovernorAction",
    "StressResult",
    "ResilienceResult",
    "CorrelationResult",
    "ConvexityResult",
    "EfficiencyResult",
    "LeverageDecision",
    "ReinvestmentDecision",
    "MarginalContribution",
    "InstitutionalPortfolioScore",
    "KillDecision",
    "PortfolioPackage",
    "PortfolioConstructionResult",
    # kelly / growth
    "KellyEngine",
    "KellyEstimate",
    "FractionalKellyEngine",
    "GeometricGrowthEngine",
    "CapitalGrowthSimulator",
    # allocation
    "DrawdownAwareAllocator",
    "PortfolioRiskBudgetEngine",
    "SleeveAllocator",
    "DynamicLeverageEngine",
    "AdaptiveReinvestmentEngine",
    "group_by_sleeve",
    # analytics
    "PortfolioCorrelationEngine",
    "PortfolioSurvivalEngine",
    "PortfolioStressEngine",
    "PortfolioResilienceEngine",
    "PortfolioConvexityEngine",
    "MarginalContributionEngine",
    "CapitalEfficiencyEngine",
    # capacity
    "PortfolioCapacityEngine",
    "PortfolioCapacityGovernor",
    # state / score / governance / attribution / audit
    "PortfolioStateMachine",
    "institutional_portfolio_score",
    "portfolio_governance_gate",
    "PortfolioKillCriteria",
    "PortfolioAttributionEngine",
    "PortfolioAttribution",
    "PortfolioAudit",
    # engine
    "PortfolioConstructionEngine",
    # errors
    "Stage14Error",
    "PortfolioGovernanceError",
]
