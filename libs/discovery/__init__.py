"""``libs.discovery`` — surviving utilities from the retired Alpha Discovery Factory.

The factory itself (factory.py, models.py, signals.py, hypotheses.py, acceptance.py,
fragility.py, half_life.py, parameter_stability.py, correlation_engine.py,
failure_dependency.py, family_concentration.py, pools.py, portfolio_geometry.py,
cagr_optimizer.py — 14 modules) was retired 2026-07-27: a complete, self-contained MT5-era
predecessor to ``libs.autodiscovery`` (51 external importers), reachable from nothing outside
its own package. See docs/graveyard.md.

What remains is genuinely alive: individual utility functions that other subsystems adopted
directly, independent of the factory that originally housed them.
"""

from __future__ import annotations

from libs.discovery.capacity import CapacityResult, capacity_estimate
from libs.discovery.monte_carlo_survival import MonteCarloSurvivalResult, monte_carlo_survival
from libs.discovery.objective import discovery_score, expected_log_growth, log_utility
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
from libs.discovery.stress_scenario import StressScenarioResult, stress_scenario
from libs.discovery.tail_risk import TailRiskResult, tail_risk

__all__ = [
    "CapacityResult",
    "CategoryStat",
    "MonteCarloSurvivalResult",
    "RegimeDiversificationResult",
    "ResearchROIResult",
    "StressScenarioResult",
    "TailRiskResult",
    "capacity_estimate",
    "discovery_score",
    "expected_log_growth",
    "log_utility",
    "monte_carlo_survival",
    "rank_categories",
    "regime_diversification",
    "research_roi",
    "stress_scenario",
    "tail_risk",
]
