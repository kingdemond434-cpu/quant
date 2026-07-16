"""Final signal selection — convert ranked candidates into BUY/SELL/FLAT decisions.

Fail-closed: a candidate becomes BUY/SELL only if EVERY rule passes (quality, confidence, EV,
edge, confirmations, capacity, crowding, portfolio contribution, execution, factor and stability
checks). If any single rule fails, the decision is FLAT with a recorded reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from libs.signal_engine.models import (
    Direction,
    SelectionResult,
    SignalPackage,
    TradeCandidate,
)

_EPS = 1e-12


@dataclass(frozen=True)
class SelectionThresholds:
    min_quality: float = 80.0
    min_confidence: float = 0.75
    min_edge: float = 50.0
    min_execution: float = 50.0
    min_confirmation: float = 0.50


def _drawdown_proxy(candidate: TradeCandidate) -> float:
    calmar = candidate.edge.expected_calmar
    if calmar <= _EPS:
        return 0.0
    return max(0.0, candidate.edge.expected_return) / calmar


def to_package(candidate: TradeCandidate) -> SignalPackage:
    """Build the Portfolio-Engine hand-off package from an approved candidate."""
    return SignalPackage(
        symbol=candidate.symbol,
        direction=candidate.direction,
        quality_score=candidate.quality.quality_score,
        confidence=candidate.confidence.confidence,
        edge_score=candidate.edge.edge_score,
        expected_return=candidate.edge.expected_return,
        expected_drawdown=_drawdown_proxy(candidate),
        expected_sharpe=candidate.edge.expected_sharpe,
        expected_sortino=candidate.edge.expected_sortino,
        expected_calmar=candidate.edge.expected_calmar,
        expected_pf=candidate.edge.expected_pf,
        expected_value=candidate.expected_value.expected_value,
        regime=candidate.regime,
        predicted_regime=candidate.predicted_regime,
        alpha_breakdown=candidate.alpha_breakdown,
        factor_exposures=candidate.factor_exposures.exposures,
        execution_score=candidate.execution.execution_score,
        capacity_score=candidate.capacity.future_capacity_score,
        crowding_score=candidate.crowding.crowding_score,
        portfolio_contribution=candidate.portfolio_context.portfolio_contribution_score,
        institutional_score=candidate.institutional.score,
    )


def _rejection_reason(c: TradeCandidate, t: SelectionThresholds) -> str | None:
    """Return the first failing rule's reason, or None if the candidate is approved."""
    conf = c.confidence.components
    checks: list[tuple[bool, str]] = [
        (c.direction is not Direction.FLAT, "no net direction"),
        (c.quality.quality_score > t.min_quality, "quality below threshold"),
        (c.confidence.confidence > t.min_confidence, "confidence below threshold"),
        (c.expected_value.positive, "expected value not positive"),
        (c.edge.edge_score > t.min_edge, "edge below threshold"),
        (conf["cross_asset_confirmation"] >= t.min_confirmation, "cross-asset not confirmed"),
        (conf["microstructure_confirmation"] >= t.min_confirmation, "microstructure not confirmed"),
        (conf["future_regime_confidence"] >= t.min_confirmation, "future regime not confirmed"),
        (c.capacity.future_capacity_score > 0.0, "no capacity available"),
        (c.crowding.acceptable, "crowding too high"),
        (c.portfolio_context.accept, "portfolio contribution not positive"),
        (c.portfolio_context.portfolio_contribution_score > 0.0, "no portfolio contribution"),
        (
            c.execution.passed and c.execution.execution_score >= t.min_execution,
            "execution infeasible",
        ),
        (c.factor_exposures.acceptable, "factor concentration violation"),
        (c.stability.passed, "signal unstable"),
    ]
    for ok, reason in checks:
        if not ok:
            return reason
    return None


def select_final_signals(
    candidates: Sequence[TradeCandidate],
    *,
    thresholds: SelectionThresholds | None = None,
) -> SelectionResult:
    """Apply the fail-closed selection rules to ranked candidates."""
    thresholds = thresholds or SelectionThresholds()
    approved: list[SignalPackage] = []
    rejected: dict[str, str] = {}
    for c in candidates:
        reason = _rejection_reason(c, thresholds)
        if reason is None:
            approved.append(to_package(c))
        else:
            rejected[c.symbol] = reason
    return SelectionResult(approved=approved, rejected=rejected)
