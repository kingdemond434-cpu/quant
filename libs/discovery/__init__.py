"""``libs.discovery`` — the Alpha Discovery Factory.

Objective: maximize expected log utility (sustainable long-term geometric growth) through a
diversified set of statistically-valid, capacity-aware, regime-robust, low-fragility,
independently-failing alphas — subject to survival > 95% and max drawdown < 20%. NOT backtest
CAGR. The factory generates economically-anchored hypotheses, runs the trials-adjusted gauntlet
and every robustness engine, and outputs only the accepted survivors.
"""

from __future__ import annotations

from libs.discovery.acceptance import AcceptanceResult, alpha_acceptance, portfolio_acceptance
from libs.discovery.cagr_optimizer import CAGROptimization, optimize_allocation
from libs.discovery.capacity import CapacityResult, capacity_estimate
from libs.discovery.correlation_engine import AlphaCorrelationResult, alpha_correlation
from libs.discovery.errors import DiscoveryError
from libs.discovery.factory import AlphaDiscoveryFactory
from libs.discovery.failure_dependency import FailureDependencyResult, failure_dependency
from libs.discovery.family_concentration import FamilyConcentrationResult, family_concentration
from libs.discovery.fragility import FragilityResult, alpha_fragility
from libs.discovery.half_life import HalfLifeResult, alpha_half_life
from libs.discovery.hypotheses import HypothesisGenerator, default_params, param_sweep
from libs.discovery.models import (
    AlphaHypothesis,
    DiscoveryCandidate,
    DiscoveryReport,
    HypothesisCategory,
    RobustnessScores,
)
from libs.discovery.monte_carlo_survival import MonteCarloSurvivalResult, monte_carlo_survival
from libs.discovery.objective import discovery_score, expected_log_growth, log_utility
from libs.discovery.parameter_stability import ParameterStabilityResult, parameter_stability
from libs.discovery.pools import SuccessorPools
from libs.discovery.portfolio_geometry import PortfolioGeometryResult, portfolio_geometry
from libs.discovery.regime_diversification import (
    RegimeDiversificationResult,
    regime_diversification,
)
from libs.discovery.research_roi import (
    CategoryStat,
    ResearchROIResult,
    rank_categories,
    research_roi,
)
from libs.discovery.signals import build_generator
from libs.discovery.stress_scenario import StressScenarioResult, stress_scenario
from libs.discovery.tail_risk import TailRiskResult, tail_risk

__all__ = [  # noqa: RUF022  # grouped by concern
    # factory + models
    "AlphaDiscoveryFactory",
    "AlphaHypothesis",
    "HypothesisCategory",
    "DiscoveryCandidate",
    "DiscoveryReport",
    "RobustnessScores",
    "HypothesisGenerator",
    "default_params",
    "param_sweep",
    "build_generator",
    # objective / optimization
    "expected_log_growth",
    "log_utility",
    "discovery_score",
    "optimize_allocation",
    "CAGROptimization",
    # robustness engines
    "alpha_fragility",
    "FragilityResult",
    "parameter_stability",
    "ParameterStabilityResult",
    "failure_dependency",
    "FailureDependencyResult",
    "regime_diversification",
    "RegimeDiversificationResult",
    "stress_scenario",
    "StressScenarioResult",
    "monte_carlo_survival",
    "MonteCarloSurvivalResult",
    "tail_risk",
    "TailRiskResult",
    "alpha_half_life",
    "HalfLifeResult",
    "capacity_estimate",
    "CapacityResult",
    "family_concentration",
    "FamilyConcentrationResult",
    "portfolio_geometry",
    "PortfolioGeometryResult",
    "alpha_correlation",
    "AlphaCorrelationResult",
    "research_roi",
    "rank_categories",
    "ResearchROIResult",
    "CategoryStat",
    # acceptance + pools
    "alpha_acceptance",
    "portfolio_acceptance",
    "AcceptanceResult",
    "SuccessorPools",
    # errors
    "DiscoveryError",
]
