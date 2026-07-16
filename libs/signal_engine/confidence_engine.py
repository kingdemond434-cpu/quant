"""Confidence engine — fuse every corroborating signal into a single 0..1 confidence.

Combines the meta-model probability, alpha agreement, current/future regime confidence,
cross-asset and microstructure confirmation, capacity confidence, and portfolio contribution.
The blend rewards broad agreement (mean) but punishes any single weak link (min), so a high
confidence requires *all* corroborations, not just one strong one (fail-closed bias).
"""

from __future__ import annotations

from libs.signal_engine.meta_model import MetaModel
from libs.signal_engine.models import ConfidenceResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ConfidenceEngine:
    """Produces a 0..1 confidence and its component breakdown."""

    def __init__(self, *, meta_model: MetaModel | None = None) -> None:
        self.meta_model = meta_model or MetaModel()

    def estimate(
        self,
        *,
        edge_score: float,
        alpha_agreement: float,
        regime_confidence: float,
        future_regime_confidence: float,
        cross_asset_confirmation: float,
        microstructure_confirmation: float,
        capacity_confidence: float,
        portfolio_contribution: float,
        persistence: float,
        stability: float,
    ) -> ConfidenceResult:
        meta = self.meta_model.predict_proba(
            edge=edge_score / 100.0,
            agreement=alpha_agreement,
            persistence=persistence,
            stability=stability,
        )
        components = {
            "meta_model": _clip01(meta),
            "alpha_agreement": _clip01(alpha_agreement),
            "regime_confidence": _clip01(regime_confidence),
            "future_regime_confidence": _clip01(future_regime_confidence),
            "cross_asset_confirmation": _clip01(cross_asset_confirmation),
            "microstructure_confirmation": _clip01(microstructure_confirmation),
            "capacity_confidence": _clip01(capacity_confidence),
            "portfolio_contribution": _clip01(portfolio_contribution),
        }
        values = list(components.values())
        mean = sum(values) / len(values)
        weakest = min(values)
        confidence = _clip01(0.5 * mean + 0.5 * weakest)
        return ConfidenceResult(confidence=confidence, components=components)
