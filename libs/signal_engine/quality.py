"""Signal quality scoring and pre-filters.

``SignalQuality`` fuses edge, confidence, persistence, stability, and agreement (scaled by the
decay weight multiplier) into a 0-100 score. ``SignalFilters`` rejects structurally unusable
candidates early (fail-closed): no governed alpha, no liquidity, or a blown-out spread.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from libs.signal_engine.models import AlphaSignal, MarketState, QualityResult

_QUALITY_THRESHOLD = 80.0


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class SignalQuality:
    """Computes the 0-100 quality score used by final selection."""

    def __init__(self, *, threshold: float = _QUALITY_THRESHOLD) -> None:
        self.threshold = threshold

    def score(
        self,
        *,
        edge_score: float,
        confidence: float,
        persistence_score: float,
        stability_score: float,
        alpha_agreement: float,
        decay_weight_multiplier: float,
    ) -> QualityResult:
        components = {
            "edge": edge_score,
            "confidence": confidence * 100.0,
            "persistence": persistence_score,
            "stability": stability_score,
            "agreement": alpha_agreement * 100.0,
        }
        base = (
            0.30 * components["edge"]
            + 0.30 * components["confidence"]
            + 0.15 * components["persistence"]
            + 0.15 * components["stability"]
            + 0.10 * components["agreement"]
        )
        quality = _clip(base * decay_weight_multiplier, 0.0, 100.0)
        return QualityResult(
            quality_score=quality, components=components, passed=quality > self.threshold
        )


@dataclass(frozen=True)
class FilterOutcome:
    ok: bool
    reason: str


class SignalFilters:
    """Cheap structural gates applied before the expensive estimation pipeline."""

    def __init__(self, *, max_spread_bps: float = 50.0) -> None:
        self.max_spread_bps = max_spread_bps

    def pre_filter(
        self, signals: Sequence[AlphaSignal], state: MarketState
    ) -> FilterOutcome:
        if not signals:
            return FilterOutcome(False, "no alpha signals")
        if not any(s.governance_passed for s in signals):
            return FilterOutcome(False, "no governed alpha (gauntlet not passed)")
        if state.liquidity_score <= 0.0:
            return FilterOutcome(False, "no liquidity")
        if state.spread_bps > self.max_spread_bps:
            return FilterOutcome(False, f"spread {state.spread_bps:.1f}bps over cap")
        return FilterOutcome(True, "ok")
