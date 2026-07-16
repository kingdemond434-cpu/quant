"""SignalEngine — the exclusive source of all BUY/SELL/FLAT decisions.

No trade may reach the Portfolio Engine, Risk Engine, or Execution Engine without passing through
here. The engine collects, validates, weights, regime-routes, confirms, scores, ranks, and
selects alpha outputs into ``SignalPackage`` objects. It is fail-closed: any missing
corroboration, failed gate, or error resolves to FLAT.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from libs.signal_engine.aggregation import SignalAggregator
from libs.signal_engine.alpha_weighting import DynamicWeighting
from libs.signal_engine.audit import SignalAudit
from libs.signal_engine.capacity import SignalCapacityForecaster
from libs.signal_engine.confidence_engine import ConfidenceEngine
from libs.signal_engine.crowding import SignalCrowdingEngine
from libs.signal_engine.decay import SignalDecayEngine
from libs.signal_engine.edge_estimator import EdgeEstimator
from libs.signal_engine.execution import ExecutionFeasibilityEngine
from libs.signal_engine.expected_value import ExpectedValueEngine
from libs.signal_engine.factor_exposure import FactorExposureEngine
from libs.signal_engine.governance import GovernanceVerdict, signal_governance_gate
from libs.signal_engine.institutional_score import institutional_signal_score
from libs.signal_engine.models import (
    AlphaSignal,
    Direction,
    MarketState,
    SelectionResult,
    TradeCandidate,
)
from libs.signal_engine.persistence import SignalPersistenceEngine, SignalStabilityEngine
from libs.signal_engine.portfolio_context import PortfolioContextEngine
from libs.signal_engine.quality import SignalFilters, SignalQuality
from libs.signal_engine.ranking import rank_trade_candidates
from libs.signal_engine.regime import RegimeRouter, transition_confidence
from libs.signal_engine.selection import SelectionThresholds, select_final_signals
from libs.signal_engine.uncertainty import SignalUncertaintyEngine

_EPS = 1e-12


class SymbolObservation(BaseModel):
    """All inputs the engine needs to evaluate one symbol on one bar."""

    model_config = ConfigDict(frozen=True)

    signals: list[AlphaSignal]
    state: MarketState
    governance_verdict: GovernanceVerdict | None = None
    # decay (rolling metrics; fall back to the edge estimate when absent)
    rolling_profit_factor: float | None = None
    rolling_sharpe: float | None = None
    # capacity / costs (basis points unless stated)
    intended_notional: float = 0.0
    edge_bps: float = 10.0
    slippage_bps: float = 1.0
    commission_frac: float = 0.0
    execution_failure_risk: float = 0.0
    latency_risk: float = 0.0
    # crowding
    avg_alpha_correlation: float = 0.0
    factor_overlap: float = 0.0
    public_crowding: float = 0.0
    # factor exposure
    factor_loadings: dict[str, dict[str, float]] = Field(default_factory=dict)
    # portfolio context
    correlation_to_portfolio: float = 0.0
    marginal_diversification: float = 1.0
    concentration_after: float = 0.0
    # uncertainty / tail
    sample_size: int = 100
    tail_risk_score: float = 0.0
    # persistence
    signal_age: int = 60
    survival: float = 1.0
    flip_frequency: float = 0.0
    noise_level: float = 0.0
    regime_consistency: float = 1.0
    # stability
    oscillation: float = 0.0
    direction_change_rate: float = 0.0
    prediction_stability: float = 1.0
    alpha_stability: float = 1.0
    regime_stability: float = 1.0


class SignalEngine:
    """Coordinates every sub-engine into the exclusive signal pipeline."""

    def __init__(
        self,
        *,
        audit: SignalAudit | None = None,
        thresholds: SelectionThresholds | None = None,
    ) -> None:
        self.filters = SignalFilters()
        self.weighting = DynamicWeighting()
        self.aggregator = SignalAggregator()
        self.router = RegimeRouter()
        self.edge_estimator = EdgeEstimator()
        self.ev_engine = ExpectedValueEngine()
        self.confidence_engine = ConfidenceEngine()
        self.persistence_engine = SignalPersistenceEngine()
        self.stability_engine = SignalStabilityEngine()
        self.decay_engine = SignalDecayEngine()
        self.crowding_engine = SignalCrowdingEngine()
        self.capacity_forecaster = SignalCapacityForecaster()
        self.factor_engine = FactorExposureEngine()
        self.execution_engine = ExecutionFeasibilityEngine()
        self.portfolio_context = PortfolioContextEngine()
        self.uncertainty_engine = SignalUncertaintyEngine()
        self.quality_engine = SignalQuality()
        self.thresholds = thresholds or SelectionThresholds()
        self.audit = audit

    def evaluate(self, observations: Sequence[SymbolObservation]) -> SelectionResult:
        """Evaluate observations and return approved packages plus FLAT reasons."""
        candidates: list[TradeCandidate] = []
        pre_flat: dict[str, str] = {}

        for obs in observations:
            outcome = self._build_candidate(obs)
            if isinstance(outcome, str):
                pre_flat[obs.state.symbol] = outcome
            else:
                candidates.append(outcome)

        ranked = rank_trade_candidates(candidates)
        selection = select_final_signals(ranked, thresholds=self.thresholds)
        merged_rejected = {**pre_flat, **selection.rejected}
        result = SelectionResult(approved=selection.approved, rejected=merged_rejected)

        if self.audit is not None:
            self.audit.record_selection(result)
        return result

    def _build_candidate(self, obs: SymbolObservation) -> TradeCandidate | str:
        """Return a TradeCandidate, or a FLAT reason string (fail-closed)."""
        signals, state = obs.signals, obs.state

        gate = self.filters.pre_filter(signals, state)
        if not gate.ok:
            return gate.reason
        if obs.governance_verdict is not None and not signal_governance_gate(
            obs.governance_verdict
        ):
            return "governance gate failed"

        weights = self.weighting.weights(signals, state)
        aggregation = self.aggregator.aggregate(signals, weights)
        if aggregation.direction is Direction.FLAT:
            return "no net direction"

        edge = self.edge_estimator.estimate(signals, weights, state)
        capacity = self.capacity_forecaster.forecast(
            adv_usd=state.adv_usd, intended_notional=obs.intended_notional, edge_bps=obs.edge_bps
        )
        ev = self.ev_engine.estimate(
            signals, weights,
            spread_bps=state.spread_bps, slippage_bps=obs.slippage_bps,
            market_impact_bps=capacity.future_market_impact_estimate,
            commission_frac=obs.commission_frac,
            execution_failure_risk=obs.execution_failure_risk,
        )
        persistence = self.persistence_engine.assess(
            signal_age=obs.signal_age, survival=obs.survival,
            flip_frequency=obs.flip_frequency, noise_level=obs.noise_level,
            regime_consistency=obs.regime_consistency,
        )
        stability = self.stability_engine.assess(
            oscillation=obs.oscillation, direction_change_rate=obs.direction_change_rate,
            prediction_stability=obs.prediction_stability, alpha_stability=obs.alpha_stability,
            regime_stability=obs.regime_stability,
        )
        decay = self.decay_engine.assess(
            profit_factor=obs.rolling_profit_factor
            if obs.rolling_profit_factor is not None
            else edge.expected_pf,
            sharpe=obs.rolling_sharpe if obs.rolling_sharpe is not None else edge.expected_sharpe,
        )
        crowding = self.crowding_engine.assess(
            avg_alpha_correlation=obs.avg_alpha_correlation,
            factor_overlap=obs.factor_overlap, public_crowding=obs.public_crowding,
        )
        factor = self.factor_engine.assess(signals, weights, loadings=obs.factor_loadings)
        execution = self.execution_engine.assess(
            spread_bps=state.spread_bps, expected_slippage_bps=obs.slippage_bps,
            market_impact_bps=capacity.future_market_impact_estimate,
            liquidity_score=state.liquidity_score, latency_risk=obs.latency_risk,
        )
        uncertainty = self.uncertainty_engine.estimate(
            alpha_agreement=aggregation.alpha_agreement, n_alphas=len(signals),
            sample_size=obs.sample_size, volatility_state=state.volatility_state,
        )
        portfolio_ctx = self.portfolio_context.evaluate(
            candidate_sharpe=edge.expected_sharpe, candidate_sortino=edge.expected_sortino,
            candidate_calmar=edge.expected_calmar,
            correlation_to_portfolio=obs.correlation_to_portfolio,
            marginal_diversification=obs.marginal_diversification,
            concentration_after=obs.concentration_after,
        )

        regime_conf = self._regime_confidence(signals, weights, state)
        same_regime = state.predicted_regime == state.regime
        future_conf = 1.0 if same_regime else transition_confidence(state)
        confidence = self.confidence_engine.estimate(
            edge_score=edge.edge_score, alpha_agreement=aggregation.alpha_agreement,
            regime_confidence=regime_conf, future_regime_confidence=future_conf,
            cross_asset_confirmation=state.cross_asset_score,
            microstructure_confirmation=state.microstructure_score,
            capacity_confidence=capacity.capacity_confidence,
            portfolio_contribution=portfolio_ctx.portfolio_contribution_score / 100.0,
            persistence=persistence.persistence_score / 100.0,
            stability=stability.stability_score / 100.0,
        )
        # Decay erodes confidence directly.
        confidence = confidence.model_copy(
            update={"confidence": confidence.confidence * decay.confidence_multiplier}
        )
        quality = self.quality_engine.score(
            edge_score=edge.edge_score, confidence=confidence.confidence,
            persistence_score=persistence.persistence_score,
            stability_score=stability.stability_score,
            alpha_agreement=aggregation.alpha_agreement,
            decay_weight_multiplier=decay.weight_multiplier,
        )
        institutional = institutional_signal_score(
            edge_score=edge.edge_score, confidence=confidence.confidence,
            capacity_score=capacity.future_capacity_score,
            persistence_score=persistence.persistence_score,
            stability_score=stability.stability_score,
            decay_weight_multiplier=decay.weight_multiplier,
            portfolio_contribution=portfolio_ctx.portfolio_contribution_score,
            execution_score=execution.execution_score,
            tail_risk_score=obs.tail_risk_score,
            uncertainty_score=uncertainty.uncertainty_score,
        )

        return TradeCandidate(
            symbol=state.symbol, direction=aggregation.direction,
            aggregated_strength=aggregation.aggregated_strength,
            alpha_agreement=aggregation.alpha_agreement, alpha_breakdown=aggregation.breakdown,
            regime=state.regime, predicted_regime=state.predicted_regime,
            edge=edge, expected_value=ev, confidence=confidence, quality=quality,
            persistence=persistence, stability=stability, decay=decay,
            factor_exposures=factor, execution=execution, crowding=crowding,
            capacity=capacity, portfolio_context=portfolio_ctx, uncertainty=uncertainty,
            tail_risk_score=obs.tail_risk_score, institutional=institutional,
        )

    def _regime_confidence(
        self, signals: Sequence[AlphaSignal], weights: Mapping[str, float], state: MarketState
    ) -> float:
        total = sum(weights.get(s.alpha_id, 0.0) for s in signals)
        if total <= _EPS:
            return 0.0
        weighted = sum(
            weights.get(s.alpha_id, 0.0) * self.router.route(s, state) for s in signals
        )
        return weighted / total
