"""L0038 / L0048 / L0054, graduated into enforcement -- the mined-evidence priority block must
reach every frontier miner, in every language, every run.

WHY PROMPT-LEVEL ENFORCEMENT IS THE RIGHT SEAM HERE. These three lessons are instructions to a
MINER, not parameters of a gate: numbers-over-mechanisms (measured 0/13 vs 4/4 conversion),
rank-noisy / z-score-expensive-to-move, and mean-reversion-last-on-crypto. The desk-memory corpus
is hard-budgeted, so lessons this operational can rank out of the injected tail -- and a lesson
that reaches no organ protects nothing. Putting the rules in the prompts the miners actually
receive, and pinning that with a test, is the "graduate into a test" exit the memory budget
demands: the lesson is demoted BECAUSE the prompt now carries it verbatim, not lost.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_ROOT = Path(__file__).resolve().parents[2]
_PROMPTS = sorted((_ROOT / "ops").glob("frontier_*_prompt.txt"))


def test_there_are_still_miner_prompts_to_enforce_on() -> None:
    """If the prompt files move, this suite must fail loudly rather than pass on an empty glob."""
    assert len(_PROMPTS) >= 5, [p.name for p in _PROMPTS]


@pytest.mark.parametrize("prompt", _PROMPTS, ids=lambda p: p.name)
def test_every_miner_prompt_carries_the_mined_evidence_priority_block(prompt: Path) -> None:
    src = prompt.read_text("utf-8")
    assert "MINED-EVIDENCE PRIORITY" in src, (
        f"{prompt.name} lost the L0038/L0048/L0054 block -- the miner it briefs is back to "
        "harvesting mechanisms that convert at 0/13")
    # The three rules, matched on their load-bearing phrases rather than exact prose.
    assert "NUMBERS OVER MECHANISMS" in src                       # L0038
    assert "Z-SCORE when it is expensive to move" in src          # L0048
    assert "mean-reversion families rank LAST" in src             # L0054


@pytest.mark.parametrize("prompt", _PROMPTS, ids=lambda p: p.name)
def test_no_prefilter_before_the_gauntlet(prompt: Path) -> None:
    """L0017, graduated: a pre-filter's false negatives are structurally invisible while its
    false positives cost one paragraph — so a miner reads everything and lets the MEASURED
    gauntlet reject. The scam filter was struck from all miner prompts on that reasoning
    (principal 2026-08-01); this keeps it struck. A prompt that reacquires a discard-before-
    reading rule silently reintroduces an unauditable filter."""
    src = prompt.read_text("utf-8")
    # Matched on the rule, not one prose form: the CN prompt says "let the GAUNTLET do the
    # rejecting", the others "let the GAUNTLET reject". Pinning one wording would fail on
    # a legitimate edit while a real pre-filter slipped past under different words.
    assert "let the GAUNTLET" in src, (
        f"{prompt.name} lost the read-it-all rule — a pre-filter can creep back in and its "
        "misses leave no trace to audit (L0017)")
