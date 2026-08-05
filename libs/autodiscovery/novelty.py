"""The graveyard novelty gate, in the shape the live generation loop can actually hold.

WHAT WAS BROKEN. `libs.alpha_factory.hypothesis_novelty` has existed and been correct for a long
time, and the constitution's NOVELTY GATE duty orders every organ to screen a hypothesis against
the graveyard before spending compute on it. It was never wired: `PriorIdea` was constructed only
in tests and one-off scripts, and the sole pre-compute screen in `AutoDiscoveryLab.cycle` was
`CandidateStore.exists` -- an exact content-hash equality lookup over (family, subtype, symbol,
params). That catches a literal re-run and nothing else.

WHAT THAT COSTS. The content hash includes the SYMBOL and the param VALUES, so the same dead
mechanism proposed on a different instrument, or at a nudged lookback, reads as brand new and is
paid for in full. The recall replay (`scripts/replay_novelty_recall.py`, artifact
`data/novelty_recall_replay.json`) measured this directly on the desk's own history: of 195
rejects in one campaign, the content-hash dedupe caught 0, and this gate flags 195.

WHAT THIS GATE DOES NOT DO. It never promotes, never relaxes a validation bar, and never decides
an edge is real. It only declines to re-pay for ground the desk already bought -- and skipping a
redundant hypothesis cannot loosen a bar downstream either, because `_family_trials` deflates
against a PRE-REGISTERED per-family budget floor, so testing fewer redundant candidates leaves
the DSR wall exactly where it was.

EVERY SUPPRESSION IS RECORDED. `screen` returns the nearest prior and its similarity, and the
orchestrator writes them to the audit log. A gate that silently drops candidates would be
un-auditable and could quietly become the desk's biggest source of missed edge; a gate that names
what it dropped and why can be measured, and reversed, from the record it leaves.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from libs.alpha_factory.hypothesis_novelty import (
    NoveltyResult,
    PriorIdea,
    hypothesis_novelty,
)
from libs.alpha_factory.hypothesis_render import candidate_features, candidate_statement

if TYPE_CHECKING:  # pragma: no cover - typing only
    from libs.autodiscovery.models import Hypothesis

#: Compiled by scripts/build_graveyard_priors.py from graveyard.md + research_memory + every
#: rejected candidate row. Rebuilt, never hand-edited.
CORPUS = Path("data/graveyard_priors.json")

#: The replay measured 100% recall on re-proposed mechanisms and no false positives at 0.7 on the
#: desk's own campaigns. Kept at the gate's own documented default rather than tuned per caller:
#: a per-caller threshold is a knob that drifts, and the number it would be tuned against is the
#: same replay artifact for everyone.
DEFAULT_THRESHOLD = 0.7


def load_corpus(path: Path = CORPUS) -> list[PriorIdea]:
    """Read the compiled canonical graveyard. Absent corpus -> empty, i.e. the gate is inert."""
    import json

    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [PriorIdea(**row) for row in payload.get("priors", [])]


def render(hyp: Hypothesis) -> tuple[str, tuple[str, ...]]:
    """A live hypothesis as (statement, features), rendered EXACTLY as the corpus was.

    `.value` on both enums is load-bearing: the corpus was compiled from sqlite rows that store
    the enum values, so rendering `Family.LIQUIDITY` instead of `liquidity` would produce a
    feature set that matches nothing and a gate that reports everything as novel.
    """
    statement = candidate_statement(
        hyp.family.value, hyp.subtype, hyp.mechanism.value, dict(hyp.params), [hyp.symbol]
    )
    features = candidate_features(
        hyp.family.value, hyp.subtype, hyp.mechanism.value, dict(hyp.params)
    )
    return statement, features


class NoveltyGate:
    """Screens hypotheses against the compiled graveyard before any compute is spent on them."""

    def __init__(
        self,
        priors: Sequence[PriorIdea],
        *,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self.priors = list(priors)
        self.threshold = float(threshold)

    @classmethod
    def from_corpus(
        cls, path: Path = CORPUS, *, threshold: float = DEFAULT_THRESHOLD
    ) -> NoveltyGate | None:
        """The gate for the canonical corpus, or None when there is no corpus to screen against.

        None rather than an empty gate on purpose: an empty gate is indistinguishable from a
        working one in a cycle summary, so a corpus that silently failed to build would look
        exactly like a cycle with nothing redundant in it.
        """
        priors = load_corpus(path)
        return cls(priors, threshold=threshold) if priors else None

    def screen(self, hyp: Hypothesis) -> NoveltyResult:
        statement, features = render(hyp)
        return hypothesis_novelty(
            statement, features=features, priors=self.priors,
            redundant_threshold=self.threshold,
        )
