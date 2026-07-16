"""Opportunity ranking — order trade candidates by the institutional score.

Ranks highest-to-lowest by the master institutional score, breaking ties by confidence then edge
so the most corroborated opportunity wins. Ranking is total and deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.signal_engine.models import TradeCandidate


def _key(c: TradeCandidate) -> tuple[float, float, float]:
    return (c.institutional.score, c.confidence.confidence, c.edge.edge_score)


def rank_trade_candidates(candidates: Sequence[TradeCandidate]) -> list[TradeCandidate]:
    """Return candidates sorted from best to worst by institutional score."""
    return sorted(candidates, key=_key, reverse=True)


class SignalRanker:
    """Object wrapper around :func:`rank_trade_candidates`."""

    def rank(self, candidates: Sequence[TradeCandidate]) -> list[TradeCandidate]:
        return rank_trade_candidates(candidates)
