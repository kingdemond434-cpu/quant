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


def _idf(priors: Sequence[PriorIdea]) -> dict[str, float]:
    """Smoothed inverse document frequency over the priors' statements.

    Weighting exists so containment (below) is not trigger-happy: desk boilerplate that appears
    in half the graveyard ("funding", "cross", "daily") earns almost no mass, while the tokens
    that actually name a mechanism dominate the match.
    """
    df: dict[str, int] = {}
    for p in priors:
        for t in _tokens(p.statement):
            df[t] = df.get(t, 0) + 1
    n = len(priors)
    import math
    return {t: 1.0 + math.log((n + 1) / (d + 1)) for t, d in df.items()}


def _stmt_similarity(statement: str, prior: PriorIdea, idf: dict[str, float],
                     n_priors: int) -> float:
    """IDF-weighted OVERLAP COEFFICIENT (containment), not Jaccard.

    R0434, measured twice (2026-07-30: 0/43; 2026-08-06: 0/50 recall): a generator presents a
    SHORT candidate statement while graveyard rows run ~1500 chars, and Jaccard between the two
    is bounded above by the length ratio — the 0.7 threshold was structurally unreachable for the
    query shape the gate actually receives (measured max 0.667), so every re-test of dead ground
    passed. Containment divides the matched mass by the SMALLER side's mass, so a short statement
    fully contained in a long prior scores ~1.0 regardless of the prior's length. Query tokens
    unseen in the whole corpus take the maximum IDF: distinctive new vocabulary is exactly what
    should pull a candidate toward novel.
    """
    import math
    a, b = _tokens(statement), _tokens(prior.statement)
    if not a or not b:
        return 0.0
    unseen = 1.0 + math.log(float(n_priors + 1))
    mass_a = sum(idf.get(t, unseen) for t in a)
    mass_b = sum(idf.get(t, unseen) for t in b)
    inter = sum(idf.get(t, unseen) for t in a & b)
    floor = min(mass_a, mass_b)
    return inter / floor if floor > 0 else 0.0


def _similarity(
    statement: str, features: Sequence[str], prior: PriorIdea,
    idf: dict[str, float], n_priors: int,
) -> float:
    """Blend statement-token overlap with feature-set overlap.

    Features encode the mechanism, so when both sides declare them they dominate (0.7) — the same
    mechanism in different words is still a re-test. When features are absent on either side, fall
    back to statement-token similarity alone. Features are short symmetric sets, so plain Jaccard
    is correct there; statements are asymmetric in length, so they use weighted containment.
    """
    stmt_sim = _stmt_similarity(statement, prior, idf, n_priors)
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
    idf = _idf(priors)
    for prior in priors:
        sim = _similarity(statement, features, prior, idf, len(priors))
        if sim > nearest_sim:
            nearest_sim, nearest_id, nearest_lesson = sim, prior.id, prior.lesson
    return NoveltyResult(
        novelty_score=1.0 - nearest_sim,
        nearest_id=nearest_id,
        nearest_similarity=nearest_sim,
        nearest_lesson=nearest_lesson,
        is_redundant=nearest_sim >= redundant_threshold,
    )
