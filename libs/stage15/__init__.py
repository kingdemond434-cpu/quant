"""``libs.stage15`` — alpha discovery, edge research & live validation factory.

The orchestration layer that turns the platform from infrastructure-rich to edge-rich: it threads
candidates through Discovery -> Validation -> Walk-Forward -> Shadow -> Paper -> Allocation ->
Monitoring -> Revalidation -> Retirement, gated by economic mechanism, regime resilience, portfolio
contribution, and a fail-closed governance gate, all under a research kill-switch. Optimized for the
*smallest* number of durable, low-correlation, economically-grounded alphas that survive live.

Reuses Architecture v1.0 throughout: ``libs.discovery`` (alpha factory, capacity, fragility,
regime diversification), ``libs.validation`` (gauntlet, economic prior, FDR, walk-forward), the
``libs.alpha_factory`` research OS, ``libs.alpha`` lifecycle/retirement, ``libs.signal_engine``
shadow deployment, and Stage 14. No duplicate abstractions; existing engines are not redefined.
"""

from __future__ import annotations

from libs.stage15.audit import ResearchAudit
from libs.stage15.contribution import AlphaContributionForecaster
from libs.stage15.economic_mechanism import EconomicMechanismEngine
from libs.stage15.governance import ResearchGovernanceEngine, alpha_governance_gate
from libs.stage15.models import (
    AlphaGovernanceVerdict,
    AlphaQualityScore,
    AlphaScores,
    ContributionForecast,
    MechanismResult,
    MechanismType,
    PipelineRecord,
    PipelineStage,
    RegimeValidationResult,
    ResearchKillDecision,
    ResearchPipelineResult,
    ResearchPriority,
    ResearchRegime,
)
from libs.stage15.orchestrator import AlphaPipelineInput, ResearchOrchestrator
from libs.stage15.priority import ResearchCandidate, ResearchPriorityEngine
from libs.stage15.regime_validation import RegimeValidationEngine
from libs.stage15.scoring import alpha_quality_score

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "MechanismType",
    "ResearchRegime",
    "PipelineStage",
    "AlphaScores",
    "AlphaQualityScore",
    "MechanismResult",
    "RegimeValidationResult",
    "ContributionForecast",
    "ResearchPriority",
    "AlphaGovernanceVerdict",
    "ResearchKillDecision",
    "PipelineRecord",
    "ResearchPipelineResult",
    # engines
    "EconomicMechanismEngine",
    "RegimeValidationEngine",
    "AlphaContributionForecaster",
    "ResearchPriorityEngine",
    "ResearchCandidate",
    "alpha_quality_score",
    # governance
    "alpha_governance_gate",
    "ResearchGovernanceEngine",
    # orchestrator + audit
    "ResearchOrchestrator",
    "AlphaPipelineInput",
    "ResearchAudit",
]
