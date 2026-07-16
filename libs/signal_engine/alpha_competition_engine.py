"""Alpha competition engine — alphas compete continuously for influence.

Each alpha earns influence proportional to its current expected risk-adjusted contribution
(Sharpe x health x durability x conviction). The allocation is stateless, so no alpha holds a
permanent preference: influence migrates every bar toward whoever is strongest right now.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.signal_engine.models import AlphaSignal

_EPS = 1e-12


class CompetitionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    influence: dict[str, float]  # alpha_id -> share (sums to ~1, or all 0)
    ranking: list[str]           # alpha_ids best -> worst
    scores: dict[str, float]


def _score(signal: AlphaSignal) -> float:
    return (
        max(0.0, signal.sharpe)
        * max(0.0, signal.health_score / 100.0)
        * max(0.0, signal.decay_multiplier)
        * max(0.0, signal.strength)
    )


class AlphaCompetitionEngine:
    """Allocates influence among alphas by current risk-adjusted strength."""

    def compete(self, signals: Sequence[AlphaSignal]) -> CompetitionResult:
        scores = {s.alpha_id: _score(s) for s in signals}
        total = sum(scores.values())
        if total <= _EPS:
            influence = dict.fromkeys(scores, 0.0)
        else:
            influence = {k: v / total for k, v in scores.items()}
        ranking = sorted(scores, key=lambda k: scores[k], reverse=True)
        return CompetitionResult(influence=influence, ranking=ranking, scores=scores)
