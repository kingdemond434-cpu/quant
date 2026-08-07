"""THE SEVEN REGIONAL MINERS ARE SEVEN HAND-MAINTAINED COPIES, so a mandate added to one is a
mandate missing from six.

This desk has now watched that exact shape three times: a seat cap hardcoded in six organs, a
reasoning literal in six more, and a reasoning block that `kimi_hunter` alone never sent -- caught
only because a fence looked for the wrong thing. There is no generator behind these prompt files,
so the cheap equivalent is a test that every region carries every standing mandate. An eighth
region added without them fails here instead of quietly mining at half depth for a month.

WHY THE PROVENANCE MANDATE IS FENCED HARDEST. `libs/research/convergence.py` can only distinguish
genuine cross-region convergence from three regions echoing one English paper if the miners record
what a finding derives from. A miner that skips the field does not produce a weaker signal -- it
produces an UNVERIFIABLE one, and the whole convergence layer degrades to nothing for every
mechanism that miner touches.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROMPTS = sorted(Path("ops").glob("frontier_*_prompt.txt"))

#: Every standing mandate, by the marker that must appear in all seven files.
MANDATES: dict[str, str] = {
    "DEPTH MANDATE": "wide-and-shallow is a failure, not a half-success",
    "DARK-FOREST MANDATE": "era-archaeology, native lexicon, diaspora tracking",
    "PROCESS MANDATE": "mine HOW the researcher worked, not only what they concluded",
    "PROVENANCE IS MANDATORY": "without it, convergence cannot be told apart from an echo",
    "BACKTEST MINER": "backtest discovery is its own extraction category, costs included",
    "CLAIMED IS NOT VERIFIED": "a mined number is ore; only a run on the desk's data is evidence",
    "TRANSLATE, DO NOT COPY": "a foreign result is untestable here; its mechanism has an analogue",
    "WORLDQUANT / PLATFORM-CORPUS MANDATE": "the largest public description of a working process",
}


def test_there_are_regional_miners_at_all() -> None:
    """If the glob stops matching, every assertion below passes vacuously -- a green test proving
    nothing, which is worse than a red one."""
    found = [p.name for p in PROMPTS]
    assert len(PROMPTS) >= 7, f"expected the seven regional miners, found {found}"


@pytest.mark.parametrize("marker", sorted(MANDATES))
def test_EVERY_REGION_CARRIES_EVERY_STANDING_MANDATE(marker: str) -> None:
    missing = [p.name for p in PROMPTS if marker not in p.read_text("utf-8", errors="ignore")]
    assert missing == [], (
        f"{marker} ({MANDATES[marker]}) is missing from {missing}. These prompts are copies with "
        "no generator, so a mandate added to one region silently skips the others -- the same "
        "drift that left kimi_hunter without a reasoning block for its entire life.")


def test_THE_PROCESS_MANDATE_ASKS_FOR_THE_FIELDS_THAT_ACTUALLY_TRANSFER() -> None:
    """A public alpha is a crowded formula; a research PROCESS transfers across regions and cannot
    decay, because it is not a position. The failure and near-miss fields matter most and are the
    ones a miner will drop first -- a documented failure with a stated cause is EVIDENCE, and free
    graveyard material."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        for field in ("DISCOVERY PATH", "TRANSFORMATIONS", "WHAT FAILED", "WHAT NEARLY WORKED",
                      "COULD NOT TEST", "UNUSUAL MARKET BEHAVIOUR"):
            assert field in src, f"{p.name} lost the '{field}' extraction field"


def test_THE_PROVENANCE_MANDATE_DISTINGUISHES_CHECKED_EMPTY_FROM_UNCHECKED() -> None:
    """The load-bearing detail, and the one most likely to be softened into a blank line. An empty
    DERIVES-FROM and a checked-empty DERIVES-FROM are OPPOSITE facts: the first is an inability to
    check, the second is evidence of independence. Collapsing them makes every unexamined finding
    look original, which is the defect the convergence module exists to refuse."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "DERIVES-FROM" in src, f"{p.name} does not ask for the derivation chain"
        assert "NONE (checked)" in src, (
            f"{p.name} does not distinguish a CHECKED-empty derivation from an unrecorded one")


def test_CONVERGENCE_IS_NEVER_SOLD_AS_A_LOWER_BAR() -> None:
    """Ten ecosystems can be wrong about the same thing, and folk finance is exactly where they
    are -- a belief is widely held because it is intuitive. Convergence buys a queue place; the
    misuse that follows naturally from the word 'confirmation' is a bar reduction."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "QUEUE PLACE, never a lower bar" in src, (
            f"{p.name} does not state that convergence buys priority rather than a weaker bar")


def test_THE_CRYPTO_MANDATE_PRIORITISES_WITHOUT_HARDCODING_A_BOUNDARY() -> None:
    """The desk trades Binance crypto, so crypto-native grounds come first -- but a priority order
    that hardened into a boundary would stop the miners exploring undug ground, which is the one
    thing L1.52 forbids outright. Both halves have to be present in every region."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "crypto-native >" in src, f"{p.name} lost the source priority order"
        assert "NEVER hardcode that as a boundary" in src, (
            f"{p.name} states a priority with no exploration escape -- a priority that cannot be "
            "left is a boundary, and unexplored ground is mandatory")


def test_THE_SEED_MAP_IS_NOT_TREATED_AS_THE_CATALOGUE() -> None:
    """Bulk-adding 450 seeds as graded cards would take the verification backlog from 8 to ~458
    and make the desk's worst-measured bottleneck an order of magnitude worse while verifying
    nothing. The miners' own rule already calls that breadth-theater."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "crypto_source_seeds.md" in src
        assert "do NOT bulk-add" in src, f"{p.name} may dump the seed map into the catalogue"


def test_AN_UNMAPPED_MECHANISM_IS_THE_INTERESTING_CASE_NOT_THE_DISCARDABLE_ONE() -> None:
    """The desk's whole feature set is the known vocabulary, so a mechanism outside it is the only
    kind that can widen the search space rather than re-search it. A miner told to extract against
    a fixed list will silently drop exactly those."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "INTERESTING case, not the discardable one" in src, (
            f"{p.name} does not tell the miner what to do with an unmapped mechanism")


def test_COST_ABSENCE_IS_ITSELF_RECORDED_AS_A_FINDING() -> None:
    """A backtest with no fees or funding is a DIFFERENT QUANTITY from the one this desk computes,
    not a slightly weaker version of it -- WS-006 measured a Holm-cleared signal dying on exactly
    that gap."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "Absence of cost accounting is itself the finding" in src


def test_THE_PLATFORM_CORPUS_MANDATE_REFUSES_TO_IMPORT_THE_SUBMISSION_BAR() -> None:
    """The one hard refusal on that ground. WorldQuant's "in-sample Sharpe >= 1.25" is a submission
    filter for an operator that runs its own out-of-sample validation and pays per accepted alpha --
    they can afford false positives because THEY bear the expensive stage. This desk bears it with
    its own capital against a deflated t of 5.236. Importing 1.25 would be an order-of-magnitude bar
    reduction wearing a respected institution's name, and it would arrive looking like rigour."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "DO NOT IMPORT THE SUBMISSION BAR" in src, f"{p.name} may adopt a foreign bar"
        assert "never as gates for ours" in src
        # the phrase wraps across a line break in the prompt, so match on the law id
        assert "L1.6" in src


def test_THE_MANDATE_PRIORITISES_OPERATORS_AND_CITES_WHY() -> None:
    """The operator taxonomy is the highest-yield artifact on the platform, and the desk has been
    caught short by it twice -- once with no unary transforms at all, once with three missing group
    operators found in a single forwarded screenshot."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "group_rank" in src and "trade_when" in src
        assert "search_operator_library.md" in src


def test_VIDEO_IS_A_GROUND_AND_THE_EMPTY_LOG_IS_NAMED_AS_A_DEFECT() -> None:
    """The log is the only evidence gate for a paid transcript unlock (GAP #26) and it has ZERO
    rows after weeks of daily digs. An empty log reads to a future session as 'video was never a
    blocker', which is the absence-reads-as-clean defect the desk keeps finding in itself."""
    for p in PROMPTS:
        src = p.read_text("utf-8", errors="ignore")
        assert "VIDEO IS A GROUND, NOT AN EXCUSE" in src
        assert "video_locked_log.md" in src
        assert "A silent skip is the defect" in src
