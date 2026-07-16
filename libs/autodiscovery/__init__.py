"""``libs.autodiscovery`` — the autonomous institutional research lab.

Continuously generates economically-declared hypotheses across 12 families, backtests them on real
data, runs the FULL validation gauntlet (CPCV/PBO/DSR/Reality-Check/Walk-Forward/economic/capacity/
fragility + shadow & paper lifecycle stages), archives every outcome to durable memory (dedup, no
retesting), and promotes survivors through Rejected→Shadow→Paper→Registry. Never allocates real
capital; REGISTRY only marks a candidate eligible for human review. Reuses Architecture v1.0
throughout (validation, discovery, signal_builder, store). Success = validated survivors, not count.
"""

from __future__ import annotations

from libs.autodiscovery.data_opportunity import DataOpportunityEngine, DataOpportunityReport
from libs.autodiscovery.errors import AutoDiscoveryError
from libs.autodiscovery.generators import GENERATORS, GeneratorSpec, net_returns, planned_hypotheses
from libs.autodiscovery.lifecycle import promote, segment_pass
from libs.autodiscovery.memory import CandidateStore, content_hash
from libs.autodiscovery.models import (
    CandidateRecord,
    CandidateStatus,
    CycleResult,
    Family,
    Hypothesis,
    MarketSeries,
    ValidationMetrics,
    ValidationVerdict,
)
from libs.autodiscovery.orchestrator import AutoDiscoveryLab, CostProvider, DataProvider
from libs.autodiscovery.prioritization import FAMILY_PRIORITY, family_rank, prioritize
from libs.autodiscovery.reports import (
    discovery_efficiency_report,
    failure_analysis_report,
    family_performance_report,
    pipeline_health_report,
    research_report,
    survivor_report,
)
from libs.autodiscovery.research_roi import ResearchROIMonitor, ResearchROIReport
from libs.autodiscovery.validation import validate

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "Family",
    "CandidateStatus",
    "MarketSeries",
    "Hypothesis",
    "ValidationMetrics",
    "ValidationVerdict",
    "CandidateRecord",
    "CycleResult",
    # generators
    "GENERATORS",
    "GeneratorSpec",
    "planned_hypotheses",
    "net_returns",
    # validation / lifecycle
    "validate",
    "promote",
    "segment_pass",
    # memory
    "CandidateStore",
    "content_hash",
    # orchestrator + prioritization
    "AutoDiscoveryLab",
    "DataProvider",
    "CostProvider",
    "prioritize",
    "family_rank",
    "FAMILY_PRIORITY",
    # data opportunity + research ROI
    "DataOpportunityEngine",
    "DataOpportunityReport",
    "ResearchROIMonitor",
    "ResearchROIReport",
    # reports
    "research_report",
    "failure_analysis_report",
    "survivor_report",
    "family_performance_report",
    "discovery_efficiency_report",
    "pipeline_health_report",
    # errors
    "AutoDiscoveryError",
]
