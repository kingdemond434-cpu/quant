"""Successor recommendations — when an alpha decays, find ranked replacements."""

from __future__ import annotations

from collections.abc import Sequence

from libs.alpha.card import AlphaCard
from libs.alpha.ranking import rank_alphas
from libs.alpha.state import AlphaState


def recommend_successors(
    candidates: Sequence[AlphaCard], decaying: AlphaCard, *, top_n: int = 3
) -> list[AlphaCard]:
    """Rank eligible replacements for a decaying alpha (same market or category)."""
    eligible = [
        card
        for card in candidates
        if card.id != decaying.id
        and card.status is not AlphaState.RETIRED
        and (card.market == decaying.market or card.category == decaying.category)
    ]
    ranked = rank_alphas(eligible)
    by_id = {card.id: card for card in eligible}
    return [by_id[r.alpha_id] for r in ranked[:top_n]]
