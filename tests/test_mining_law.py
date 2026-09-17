"""The mining law (principal 2026-09-17, ledger M18): the intelligence, moat, exploration,
exploitation, transfer, residual, literature, program-search and meta-research systems exist to
maximise the quantity and diversity of falsifiable, implementation-ready, economically distinct
candidate edges delivered to the canonical gauntlet. They never lower validation standards,
promote capital or optimise raw candidate count. The law is written in LAWS.md, restated by the
mining objective organ, and the separation of powers is checked on the real tree."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAWS = ROOT / "docs" / "LAWS.md"

PHRASES = (
    "maximise the quantity and diversity of falsifiable, implementation-ready, economically "
    "distinct candidate edges",
    "never lower validation standards",
    "candidate quantity has zero intrinsic value",
    "Mining maximises the opportunity set",
    "the gauntlet maximises truth",
    "forward evidence validates reality",
    "the allocator maximises growth",
)


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def test_the_law_is_written_in_laws_md() -> None:
    text = LAWS.read_text(encoding="utf-8")
    assert "## 5b. THE MINING LAW" in text
    norm = _norm(text)
    for phrase in PHRASES:
        assert _norm(phrase) in norm, phrase


def test_the_mining_objective_restates_the_same_law() -> None:
    for p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT / "desks" / "mt5"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import mining_objective

    law = _norm(str(mining_objective.LAW))
    for phrase in ("mining maximises the opportunity set", "zero intrinsic value",
                   "gauntlet", "allocator"):
        assert phrase in law, phrase


def test_no_mining_organ_writes_the_book_or_the_promoter_inputs() -> None:
    for p in (str(ROOT / "desks" / "mt5" / "research"), str(ROOT / "desks" / "mt5"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import mining_objective

    verdict = mining_objective.separation_of_powers()
    assert verdict["ok"] is True, verdict.get("violations")
