"""Pre-compute hypothesis novelty gate — RD-Agent trace-conditioning, applied to avoid re-digging.

RD-Agent conditions every new proposal on the full trace of past experiments; crucially it does not
re-propose ideas close to ones already tried and failed. This desk's documented objection to
automated generation (`GAP_ANALYSIS.md`) is exactly that risk: a generator over the same data
re-discovers the graveyard at real compute cost. `strategy_similarity_engine` already de-dupes but
only AFTER a strategy is built (it needs a returns series); this gate runs BEFORE compute, scoring a
candidate hypothesis's statement + feature set against the durable record of already-FAILED ideas,
so scarce backtest compute and trials-ledger budget go only to genuinely novel hypotheses.

It also serves the live frontier-miner / prospector diggers (not just the orphaned auto-generator):
any workflow that proposes a hypothesis can screen it against the graveyard first. Advisory by
design — it returns a novelty score and the nearest prior failure (with its lesson), never a hard
block. No AI-oracle: deterministic set/token similarity, no model deciding anything.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

_TOKEN = re.compile(r"[a-z0-9]+")


class PriorIdea(BaseModel):
    """A previously-tested (typically failed) idea to screen a candidate against."""

    model_config = ConfigDict(frozen=True)

    id: str
    statement: str
    category: str = ""
    features: tuple[str, ...] = ()
    lesson: str | None = None


class NoveltyResult(BaseModel):
    """How novel a candidate is versus the graveyard, and the nearest prior it resembles."""

    model_config = ConfigDict(frozen=True)

    novelty_score: float  # 1.0 = nothing like it tried; 0.0 = exact match to a prior
    nearest_id: str | None
    nearest_similarity: float
    nearest_lesson: str | None
    is_redundant: bool

    def __bool__(self) -> bool:
        # truthy == worth testing (novel enough); redundant candidates are falsy
        return not self.is_redundant


def _tokens(text: str) -> set[str]:
    """Content tokens of a statement: lowercase alnum words of length >= 3 (crude stopword drop)."""
    return {t for t in _TOKEN.findall(text.lower()) if len(t) >= 3}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _similarity(
    statement: str, features: Sequence[str], prior: PriorIdea
) -> float:
    """Blend statement-token overlap with feature-set overlap.

    Features encode the mechanism, so when both sides declare them they dominate (0.7) — the same
    mechanism in different words is still a re-test. When features are absent on either side, fall
    back to statement-token similarity alone.
    """
    stmt_sim = _jaccard(_tokens(statement), _tokens(prior.statement))
    if features and prior.features:
        feat_sim = _jaccard(set(features), set(prior.features))
        return 0.7 * feat_sim + 0.3 * stmt_sim
    return stmt_sim


def hypothesis_novelty(
    statement: str,
    *,
    features: Sequence[str] = (),
    priors: Sequence[PriorIdea],
    redundant_threshold: float = 0.7,
) -> NoveltyResult:
    """Score a candidate hypothesis against prior (failed) ideas before spending compute on it.

    Returns the nearest prior, the similarity to it, a novelty score (``1 - nearest_similarity``),
    and whether the candidate is redundant (``nearest_similarity >= redundant_threshold``). With no
    priors the candidate is maximally novel. Advisory only — the caller decides whether to proceed.
    """
    nearest_id: str | None = None
    nearest_sim = 0.0
    nearest_lesson: str | None = None
    for prior in priors:
        sim = _similarity(statement, features, prior)
        if sim > nearest_sim:
            nearest_sim, nearest_id, nearest_lesson = sim, prior.id, prior.lesson
    return NoveltyResult(
        novelty_score=1.0 - nearest_sim,
        nearest_id=nearest_id,
        nearest_similarity=nearest_sim,
        nearest_lesson=nearest_lesson,
        is_redundant=nearest_sim >= redundant_threshold,
    )
