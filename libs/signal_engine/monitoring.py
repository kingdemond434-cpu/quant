"""Monitoring exports — aggregate signal metrics for dashboards.

Pure, deterministic aggregation over the evaluated candidates and the final selection. No I/O.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.signal_engine.models import MonitoringSnapshot, SelectionResult, TradeCandidate


def _avg(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_monitoring_snapshot(
    candidates: Sequence[TradeCandidate], selection: SelectionResult
) -> MonitoringSnapshot:
    """Summarize a signal-engine run into dashboard metrics."""
    metrics = {
        "n_candidates": len(candidates),
        "n_approved": len(selection.approved),
        "n_flat": len(selection.rejected),
        "avg_quality": _avg([c.quality.quality_score for c in candidates]),
        "avg_confidence": _avg([c.confidence.confidence for c in candidates]),
        "avg_edge": _avg([c.edge.edge_score for c in candidates]),
        "avg_decay_multiplier": _avg([c.decay.weight_multiplier for c in candidates]),
        "avg_stability": _avg([c.stability.stability_score for c in candidates]),
        "avg_persistence": _avg([c.persistence.persistence_score for c in candidates]),
        "avg_crowding": _avg([c.crowding.crowding_score for c in candidates]),
        "avg_execution": _avg([c.execution.execution_score for c in candidates]),
        "avg_capacity": _avg([c.capacity.future_capacity_score for c in candidates]),
        "avg_portfolio_contribution": _avg(
            [c.portfolio_context.portfolio_contribution_score for c in candidates]
        ),
        "avg_institutional_score": _avg([c.institutional.score for c in candidates]),
        "alpha_contributions": {
            c.symbol: c.alpha_breakdown for c in candidates
        },
    }
    return MonitoringSnapshot(metrics=metrics)
