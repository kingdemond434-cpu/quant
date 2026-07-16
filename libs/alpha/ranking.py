"""Alpha ranking — a robustness-weighted composite, decay- and overfitting-penalized."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.alpha.card import AlphaCard


class RankedAlpha(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    rank: int
    score: float


def _score(card: AlphaCard) -> float:
    sharpe = card.live_sharpe if card.live_sharpe is not None else (card.expected_sharpe or 0.0)
    pbo_penalty = 1.0 - (card.pbo if card.pbo is not None else 0.0)
    decay_penalty = 1.0 - max(0.0, min(1.0, card.decay_score))
    return max(0.0, sharpe) * max(0.0, pbo_penalty) * decay_penalty


def rank_alphas(cards: Sequence[AlphaCard]) -> list[RankedAlpha]:
    """Rank alphas by decay-/overfitting-adjusted risk-adjusted return (descending)."""
    scored = sorted(
        ((card, _score(card)) for card in cards),
        key=lambda pair: (pair[1], pair[0].expected_cagr or 0.0),
        reverse=True,
    )
    return [
        RankedAlpha(alpha_id=card.id, rank=i, score=score)
        for i, (card, score) in enumerate(scored, start=1)
    ]
