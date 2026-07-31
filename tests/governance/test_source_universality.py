"""L1.34 -- every seat's brief carries the full source-class mandate. No seat narrower than another."""
from __future__ import annotations

from pathlib import Path

import pytest

_PROMPTS = sorted(Path("ops").glob("*prompt*.txt"))
#: the classes that must be reachable from EVERY seat -- a brief missing one silently narrows it
_CLASSES = ("BACKTEST", "STRATEGY CODE", "DATASET", "AI-QUANT STRUCTURE",
            "UNTESTED ALPHA", "VIDEO")


def test_every_miner_prompt_exists():
    assert len(_PROMPTS) >= 11                       # 7 frontier regions + 4 dig seats


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


def test_untested_is_framed_as_an_unpriced_option_not_a_negative():
    # The framing is load-bearing: a seat that reads "untested" as "unproven" skips the vein.
    for src in (Path("ops/frontier_en_prompt.txt"), Path("scripts/kimi_hunter.py"),
                Path("ops/principal_doctrine.txt")):
        assert "unpriced option" in src.read_text("utf-8").lower()


def test_third_party_agent_tooling_is_mine_not_install():
    # Supply-chain rule: AI-quant structures are read as text, never executed on desk hardware.
    doc = Path("ops/principal_doctrine.txt").read_text("utf-8").lower()
    assert "never installed or run on desk hardware" in doc


def test_law_present_and_mapped():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.34 EVERY FORM OF RAW INFORMATION IS IN SCOPE FOR EVERY SEAT" in const
    assert "pay to reconstruct" in const
    assert '"L1.34"' in Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
