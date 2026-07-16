"""``libs.signal_engine`` — Stage 13.5 institutional signal intelligence engine.

The exclusive source of every BUY/SELL/FLAT decision. It transforms validated alpha outputs into
high-conviction trading decisions: weighting votes, routing by current and predicted regime,
confirming across assets and microstructure, estimating edge and expected value, scoring
confidence/quality/persistence/stability/decay, forecasting capacity, checking crowding, factor
concentration, execution feasibility and portfolio contribution, then ranking by a single
institutional score and selecting fail-closed. Only a ``SignalPackage`` may reach the Portfolio
Engine, and only after the validation gauntlet has passed.

Reuses Architecture v1.0: ``libs.costs`` (frictions), ``libs.discovery`` (capacity, tail risk),
``libs.self_improvement`` (decay classification), and the immutable ``libs.store`` audit log.
"""

from __future__ import annotations

from libs.signal_engine.aggregation import Aggregation, SignalAggregator
from libs.signal_engine.alpha_competition_engine import (
    AlphaCompetitionEngine,
    CompetitionResult,
)
from libs.signal_engine.alpha_weighting import AlphaWeighting, DynamicWeighting
from libs.signal_engine.attribution import AttributionResult, SignalAttributionEngine
from libs.signal_engine.audit import SignalAudit
from libs.signal_engine.capacity import SignalCapacityForecaster
from libs.signal_engine.champion_challenger import (
    ABTestResult,
    ChampionChallenger,
    VariantMetrics,
)
from libs.signal_engine.confidence_engine import ConfidenceEngine
from libs.signal_engine.crowding import SignalCrowdingEngine
from libs.signal_engine.decay import SignalDecayEngine
from libs.signal_engine.edge_estimator import EdgeEstimator
from libs.signal_engine.engine import SignalEngine, SymbolObservation
from libs.signal_engine.errors import SignalEngineError, SignalGovernanceError
from libs.signal_engine.execution import ExecutionFeasibilityEngine
from libs.signal_engine.expected_value import ExpectedValueEngine
from libs.signal_engine.factor_exposure import FactorExposureEngine
from libs.signal_engine.governance import (
    GovernanceVerdict,
    require_governance,
    signal_governance_gate,
)
from libs.signal_engine.institutional_score import institutional_signal_score
from libs.signal_engine.market_impact_forecaster import ImpactForecast, MarketImpactForecaster
from libs.signal_engine.meta_model import MetaModel
from libs.signal_engine.models import (
    AlphaSignal,
    CapacityForecast,
    ConfidenceResult,
    CrowdingResult,
    DecayLevel,
    Direction,
    EdgeEstimate,
    ExecutionFeasibility,
    ExpectedValueResult,
    FactorExposureResult,
    InstitutionalScore,
    MarketState,
    MonitoringSnapshot,
    PersistenceResult,
    PortfolioContextResult,
    QualityResult,
    Regime,
    SelectionResult,
    SignalDecayResult,
    SignalPackage,
    StabilityResult,
    TradeCandidate,
    UncertaintyResult,
)
from libs.signal_engine.monitoring import build_monitoring_snapshot
from libs.signal_engine.persistence import SignalPersistenceEngine, SignalStabilityEngine
from libs.signal_engine.portfolio_context import PortfolioContextEngine
from libs.signal_engine.quality import SignalFilters, SignalQuality
from libs.signal_engine.ranking import SignalRanker, rank_trade_candidates
from libs.signal_engine.regime import (
    RegimeRouter,
    RegimeTransitionRouter,
    transition_confidence,
)
from libs.signal_engine.selection import (
    SelectionThresholds,
    select_final_signals,
    to_package,
)
from libs.signal_engine.shadow import ShadowDeployment, ShadowResult
from libs.signal_engine.signal_embedding_engine import SignalEmbeddingEngine
from libs.signal_engine.stress_signal_engine import StressResult, StressSignalEngine
from libs.signal_engine.uncertainty import SignalUncertaintyEngine, signal_tail_risk

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
    "Direction",
    "Regime",
    "AlphaSignal",
    "MarketState",
    "EdgeEstimate",
    "ExpectedValueResult",
    "ConfidenceResult",
    "QualityResult",
    "PersistenceResult",
    "StabilityResult",
    "SignalDecayResult",
    "FactorExposureResult",
    "ExecutionFeasibility",
    "CrowdingResult",
    "CapacityForecast",
    "PortfolioContextResult",
    "UncertaintyResult",
    "InstitutionalScore",
    "TradeCandidate",
    "SignalPackage",
    "SelectionResult",
    "MonitoringSnapshot",
    "DecayLevel",
    # engines
    "SignalEngine",
    "SymbolObservation",
    "SignalAggregator",
    "Aggregation",
    "AlphaWeighting",
    "DynamicWeighting",
    "RegimeRouter",
    "RegimeTransitionRouter",
    "transition_confidence",
    "EdgeEstimator",
    "ExpectedValueEngine",
    "ConfidenceEngine",
    "MetaModel",
    "SignalPersistenceEngine",
    "SignalStabilityEngine",
    "SignalDecayEngine",
    "SignalCrowdingEngine",
    "SignalCapacityForecaster",
    "FactorExposureEngine",
    "ExecutionFeasibilityEngine",
    "PortfolioContextEngine",
    "SignalUncertaintyEngine",
    "signal_tail_risk",
    "SignalQuality",
    "SignalFilters",
    "SignalEmbeddingEngine",
    "MarketImpactForecaster",
    "ImpactForecast",
    "AlphaCompetitionEngine",
    "CompetitionResult",
    "StressSignalEngine",
    "StressResult",
    "SignalAttributionEngine",
    "AttributionResult",
    "ChampionChallenger",
    "VariantMetrics",
    "ABTestResult",
    "ShadowDeployment",
    "ShadowResult",
    # scoring / ranking / selection
    "institutional_signal_score",
    "rank_trade_candidates",
    "SignalRanker",
    "select_final_signals",
    "to_package",
    "SelectionThresholds",
    # governance / audit / monitoring
    "GovernanceVerdict",
    "signal_governance_gate",
    "require_governance",
    "SignalAudit",
    "build_monitoring_snapshot",
    # errors
    "SignalEngineError",
    "SignalGovernanceError",
]
