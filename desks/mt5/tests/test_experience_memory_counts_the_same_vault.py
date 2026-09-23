"""ONE WORD, ONE MEANING: `collected` must mean the same number in both organs.

`semantic_memory.build` counts the documents it read out of the vault and publishes that as
`manifest.n_docs`. `semantic_memory.distil` recounts the SAME vault to split it into the positive
and negative experience classes (Tier-1 Q17) and publishes `n_docs` of its own. Two counters over
one corpus is exactly the shape that drifts: one adds a source, the other does not, and six weeks
later two reports disagree about how much the desk knows, with nothing failing.

MEASURED 2026-09-23 on this box: build 2,155 docs, distil 2,155 docs, 58 positive / 850 negative.
These tests fail the moment those two definitions come apart -- on the real index when one exists,
and always on a synthetic corpus built here, so the guard holds on a clean checkout too.

They also pin the PARTITION: every document is positive, negative, or neither by an explicit rule
(a commit, a claim or a genome is neither), and nothing may be BOTH. A document counted twice is
how a corpus quietly inflates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import semantic_memory as sm  # noqa: E402


def _corpus() -> list[sm.Doc]:
    """One document of every kind the splitter has a rule for, plus kinds it must leave out."""
    return [
        sm.Doc("survivor:a", "survivor", "gold session breakout survived",
               {"family": "session_range_breakout", "symbol": "XAUUSD",
                "asset_class": "metals"}),
        sm.Doc("verdict:pass", "verdict", "cleared the cost gate",
               {"passed": True, "stage": "stress_costs", "family": "carry"}),
        sm.Doc("verdict:fail", "verdict", "died at the cost gate",
               {"passed": False, "stage": "stress_costs", "family": "carry"}),
        sm.Doc("verdict:leak", "verdict", "future information reached the construction",
               {"passed": False, "stage": "pit_canary", "family": "gap"}),
        sm.Doc("hyp:dead", "hypothesis", "buried", {"fate": "BURIED", "family": "trend"}),
        sm.Doc("hyp:cert", "hypothesis", "certified", {"fate": "CERTIFIED", "family": "trend"}),
        sm.Doc("trade:win", "trade_outcome", "sleeve made money", {"sum_r": 3.5}),
        sm.Doc("trade:lose", "trade_outcome", "sleeve lost money", {"sum_r": -2.0}),
        sm.Doc("lesson:1", "lesson", "a recorded failure with a cost", {}),
        # Neither class, deliberately: these carry no outcome to learn from.
        sm.Doc("commit:1", "commit", "did something to the desk", {}),
        sm.Doc("claim:1", "claim", "someone on a forum said", {}),
        sm.Doc("genome:1", "genome", "a structural fingerprint", {}),
    ]


def test_build_and_distil_report_the_same_vault_size(tmp_path: Path) -> None:
    """The REAL index, when this box has one: two organs, one number."""
    home = sm.home()
    if not (home / "index.npz").exists():
        pytest.skip(f"no semantic index on this box ({home}) -- UNMEASURED, not a pass")
    mem = sm.Memory.load()
    doc = sm.distil(out=tmp_path / "experience.json")
    assert doc["n_docs"] == mem.manifest.n_docs, (
        f"`collected` has two meanings again: build says {mem.manifest.n_docs} documents and "
        f"distil says {doc['n_docs']}. One organ has gained or lost a source the other has not.")


def test_distil_counts_exactly_what_it_was_given(tmp_path: Path) -> None:
    """On a synthetic corpus, so the guard holds on a clean checkout with no index."""
    rows = _corpus()
    doc = sm.distil(rows, out=tmp_path / "experience.json")
    assert doc["n_docs"] == len(rows)
    assert doc["status"] == "MEASURED"
    assert (tmp_path / "experience.json").exists()
    written = json.loads((tmp_path / "experience.json").read_text("utf-8"))
    assert written["n_docs"] == doc["n_docs"]


def test_positive_and_negative_partition_the_corpus(tmp_path: Path) -> None:
    """No document is in both classes, and the counts add up to what the splitter claims."""
    rows = _corpus()
    pos = sm.positive(rows)
    neg = sm.negative(rows)
    pos_ids = {d.doc_id for d in pos}
    neg_ids = {d.doc_id for d in neg}
    assert not (pos_ids & neg_ids), f"counted twice: {sorted(pos_ids & neg_ids)}"
    doc = sm.distil(rows, out=tmp_path / "experience.json")
    assert doc["n_positive"] == len(pos)
    assert doc["n_negative"] == len(neg)
    assert doc["n_positive"] + doc["n_negative"] <= doc["n_docs"]
    # The rules, pinned by their outcome rather than by their implementation.
    assert "survivor:a" in pos_ids and "verdict:pass" in pos_ids and "hyp:cert" in pos_ids
    assert "verdict:fail" in neg_ids and "hyp:dead" in neg_ids and "lesson:1" in neg_ids
    assert "trade:win" in pos_ids and "trade:lose" in neg_ids
    assert not (pos_ids | neg_ids) & {"commit:1", "claim:1", "genome:1"}


def test_every_negative_class_is_reachable_from_a_gate_name(tmp_path: Path) -> None:
    """The six classes are DERIVED from the terminal gate; `other` is a real class, not a hole."""
    doc = sm.distil(_corpus(), out=tmp_path / "experience.json")
    assert set(doc["negative"]) == {n for n, _ in sm.NEGATIVE_CLASSES} | {"other"}
    assert doc["negative"]["cost_killed"]["n"] >= 1
    assert doc["negative"]["leakage"]["n"] >= 1
    assert sm.negative_class("stress_costs") == "cost_killed"
    assert sm.negative_class("pit_canary") == "leakage"
    assert sm.negative_class("a gate nobody has written yet") == "other"
