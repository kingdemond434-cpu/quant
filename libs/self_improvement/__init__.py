"""``libs.self_improvement`` — Stage 13 supervisory self-improvement layer.

The supervisory intelligence above all trading components. It continuously scores, reweights,
reallocates, retires, reactivates, and prioritizes research across validated alphas — but it
**recommends and schedules; it does not trade**. Every production weight change requires
Portfolio Engine approval, and no learned policy deploys without passing the validation gauntlet.

Reuses Architecture v1.0 throughout: ``libs.alpha`` (lifecycle/health/decay/registry/audit),
``libs.portfolio`` (allocation/approval), ``libs.discovery`` (research ROI), and the immutable
``libs.store`` audit log. No duplicate abstractions; single source of truth.
"""

from __future__ import annotations

from libs.self_improvement.audit import ImprovementAudit
from libs.self_improvement.capital_reallocator import CapitalReallocator
from libs.self_improvement.controller import ImprovementController
from libs.self_improvement.decay_engine import AlphaDecayEngine, classify_decay
from libs.self_improvement.drift_detector import (
    AlphaDriftDetector,
    DriftResult,
    population_stability_index,
)
from libs.self_improvement.ensemble_optimizer import EnsembleOptimizer
from libs.self_improvement.errors import GovernanceError, SelfImprovementError
from libs.self_improvement.health_monitor import AlphaHealthMonitor
from libs.self_improvement.kill_switch import AlphaKillSwitch
from libs.self_improvement.lifecycle_actions import apply_reactivation, apply_retirement
from libs.self_improvement.marketplace import AlphaMarketplace
from libs.self_improvement.meta_learning import (
    MetaLearningEngine,
    meta_learning_governance_gate,
)
from libs.self_improvement.models import (
    AlphaCategory,
    DecayAssessment,
    DecayLevel,
    HealthAssessment,
    HealthLevel,
    ImprovementAction,
    ImprovementActionType,
    ImprovementPlan,
    MetaInsight,
    ResearchPriority,
    WeightProposal,
)
from libs.self_improvement.research_priority import ResearchPriorityEngine
from libs.self_improvement.weight_optimizer import DynamicWeightOptimizer, WeightCandidate

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "HealthLevel",
    "DecayLevel",
    "AlphaCategory",
    "ImprovementActionType",
    "ImprovementAction",
    "ImprovementPlan",
    "WeightProposal",
    "ResearchPriority",
    "MetaInsight",
    "HealthAssessment",
    "DecayAssessment",
    # engines
    "AlphaHealthMonitor",
    "AlphaDecayEngine",
    "classify_decay",
    "DynamicWeightOptimizer",
    "WeightCandidate",
    "CapitalReallocator",
    "ResearchPriorityEngine",
    "EnsembleOptimizer",
    "MetaLearningEngine",
    "meta_learning_governance_gate",
    "AlphaKillSwitch",
    "AlphaDriftDetector",
    "DriftResult",
    "population_stability_index",
    "AlphaMarketplace",
    # lifecycle apply-side (reuse manager)
    "apply_retirement",
    "apply_reactivation",
    # controller + audit
    "ImprovementController",
    "ImprovementAudit",
    # errors
    "SelfImprovementError",
    "GovernanceError",
]
