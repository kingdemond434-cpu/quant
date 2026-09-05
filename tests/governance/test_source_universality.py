"""L1.34 -- every seat's brief carries the full source-class mandate; no seat narrower."""
from __future__ import annotations

from pathlib import Path

import pytest

#: A ROUTER picks which grounds run today and hands the miner that ground's standing brief; it
#: carries no doctrine of its own by design, so asserting a brief's mandates against it measures
#: nothing. It is identified STRUCTURALLY -- by the fact that it points at the briefs -- and
#: `test_a_router_delegates_only_to_briefs_that_carry_the_mandate` below holds it to that, so the
#: mandate is still enforced on everything a router can actually send a miner to read.
_DELEGATION = "ops/frontier_<region>_prompt.txt"

_ALL_PROMPTS = sorted(Path("ops").glob("*prompt*.txt"))
_ROUTERS = [p for p in _ALL_PROMPTS if _DELEGATION in p.read_text("utf-8", errors="ignore")]
_PROMPTS = [p for p in _ALL_PROMPTS if p not in _ROUTERS]
#: the classes that must be reachable from EVERY seat -- a brief missing one silently narrows it
_CLASSES = ("BACKTEST", "STRATEGY CODE", "DATASET", "AI-QUANT STRUCTURE",
            "UNTESTED ALPHA", "VIDEO")


def test_every_miner_prompt_exists():
    assert len(_PROMPTS) >= 11                       # 7 frontier regions + 4 dig seats


def test_a_router_delegates_only_to_briefs_that_carry_the_mandate():
    """A router is exempt from the source-class mandate only while its hand-off is real.

    So the exemption is bought back here: every brief a router can send a miner to must exist and
    must itself carry the full mandate. Without this, `_DELEGATION` would be an opt-out that any
    prompt could claim by mentioning a path.
    """
    for r in _ROUTERS:
        for region in ("en", "cn", "ru", "jp", "kr", "ar", "br"):
            brief = Path("ops") / f"frontier_{region}_prompt.txt"
            assert brief.exists(), f"{r.name} routes to {brief}, which does not exist"
            t = brief.read_text("utf-8").upper()
            assert "RAW-INFORMATION UNIVERSALITY" in t, f"{brief.name} via {r.name}"
            for cls in _CLASSES:
                assert cls in t, (f"{brief.stem} (reached via {r.stem}) cannot see "
                                 f"source class {cls}")


@pytest.mark.parametrize("p", _PROMPTS, ids=lambda p: p.stem)
def test_every_miner_brief_carries_the_mandate(p):
    t = p.read_text("utf-8").upper()
    assert "RAW-INFORMATION UNIVERSALITY" in t
    for cls in _CLASSES:
        assert cls in t, f"{p.stem} cannot see source class {cls}"


def test_kimi_the_only_non_claude_hunter_carries_it():
    t = Path("scripts/kimi_hunter.py").read_text("utf-8").upper()
    assert "EVERY FORM OF RAW INFORMATION IS IN SCOPE" in t
    for cls in ("BACKTEST", "UNTESTED ALPHA", "VIDEO", "JOB POSTING"):
        assert cls in t


# WHY THESE THREE FENCES MOVED OFF `ops/principal_doctrine.txt` (2026-09-05).
# That file was COMPACTED by principal order on 2026-08-25: it says so in its own second paragraph
# -- "the sprawling duty text that used to live here is compacted there", meaning docs/LAWS.md and
# docs/RESEARCH.md, "with zero law regression". The fences kept pinning the file the text left, so
# they went red on a compaction that was deliberate and lossless, and a red fence that is wrong
# about where a rule lives eventually gets satisfied by pasting the rule back into the wrong file.
# The rules are unchanged and every assertion below is the same assertion; only the address moved,
# onto the canonical documents. Where a seat must ALSO carry the rule, the seat is still checked.


def test_untested_is_framed_as_an_unpriced_option_not_a_negative():
    # The framing is load-bearing: a seat that reads "untested" as "unproven" skips the vein.
    for src in (Path("ops/frontier_en_prompt.txt"), Path("scripts/kimi_hunter.py"),
                Path("docs/CONSTITUTION.md")):
        assert "unpriced option" in src.read_text("utf-8").lower()


def test_third_party_agent_tooling_is_mine_not_install():
    # Supply-chain rule: AI-quant structures are read as text, never executed on desk hardware.
    law = Path("docs/LAWS.md").read_text("utf-8").lower()
    assert "never install or run third-party agent tooling on desk hardware" in law
    # and the seats that act on it must carry it too, or the law binds nobody who is reading
    assert "third-party agent tooling on desk hardware" in (
        Path("ops/frontier_common.txt").read_text("utf-8").lower())


def test_law_present_and_mapped():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.34 EVERY FORM OF RAW INFORMATION IS IN SCOPE FOR EVERY SEAT" in const
    assert "pay to reconstruct" in const
    assert '"L1.34"' in Path("scripts/build_enforcement_matrix.py").read_text("utf-8")


# --- L1.35 deep-forest exhaustiveness ---------------------------------------------------------

@pytest.mark.parametrize("p", _PROMPTS, ids=lambda p: p.stem)
def test_every_seat_carries_the_deep_forest_mandate(p):
    t = p.read_text("utf-8")
    assert "DEEP-FOREST EXHAUSTIVENESS" in t
    # the distinction that makes it enforceable rather than a slogan
    assert "SECTION-EXHAUSTION" in t and "SEAT-EXHAUSTION IS ALWAYS FALSE" in t


def test_seat_exhaustion_is_a_defect_not_a_state():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.35 THE HUNTERS ARE THE NEVER-FINISHED ORGAN" in const
    assert "there is nothing left to hunt" in const      # named, and named as a defect
    assert "SEAT-EXHAUSTION IS ALWAYS FALSE" in Path("docs/LAWS.md").read_text("utf-8")


def test_boring_is_named_as_an_edge():
    # The insight is load-bearing: seats skip unglamorous sources unless told they are the edge.
    for f in (Path("ops/frontier_en_prompt.txt"), Path("docs/CONSTITUTION.md")):
        assert "boring" in f.read_text("utf-8").lower()


def test_law_is_mapped_to_fences():
    assert '"L1.35"' in Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
