"""BUILD-DEFERRAL IS A DEFECT (L1.56), AND IT NEEDS A FENCE BECAUSE IT IS SELF-JUSTIFYING.

MEASURED 2026-08-08. The principal asked for a list of capabilities. The desk produced an
accurate, well-evidenced account of why the highest-value item on it was not being done -- every
clause true, citing real laws (L2.9 unwired capability, L1.52 build-over-execute). It was still a
failure, because the output of a cycle is capability and a rationale is not capability.

THAT IS WHAT MAKES THIS DEFECT DANGEROUS: it arrives wearing the desk's own discipline. Every
other timidity has a tell -- "probably fine", "good enough", "later". This one cites the
constitution. So the fence is textual and lives beside the laws it protects: the doctrine text
injected into EVERY model call must carry the correction, and the law must keep the distinction
that the excuse depends on collapsing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_DOCTRINE = Path("ops/principal_doctrine.txt")
_CONST = Path("docs/CONSTITUTION.md")


def _norm(p: Path) -> str:
    return " ".join(p.read_text("utf-8").split())


@pytest.fixture(scope="module")
def doctrine() -> str:
    return _norm(_DOCTRINE)


@pytest.fixture(scope="module")
def const() -> str:
    return _norm(_CONST)


def test_THE_DOCTRINE_CARRIES_IT_BECAUSE_THAT_IS_THE_TEXT_ORGANS_ACTUALLY_READ(doctrine) -> None:
    """The constitution is a document an organ may or may not open. The doctrine is injected into
    every model call, so a law that exists only in the constitution binds nobody at runtime."""
    assert "BUILD-DEFERRAL IS A DEFECT" in doctrine


def test_THE_TWO_RULES_ARE_KEPT_APART(doctrine, const) -> None:
    """`wire it on arrival` and `do not build it` are OPPOSITE instructions. The excuse works only
    by collapsing them, so both texts must state the distinction explicitly."""
    for text in (doctrine, const):
        assert "WIRE IT ON ARRIVAL" in text
        assert "BLOAT IS UNWIRED CAPABILITY, NOT CAPABILITY" in text


def test_A_REPEATED_REQUEST_IS_TREATED_AS_A_DESK_DEFECT(doctrine, const) -> None:
    """Answering a restated requirement with reasoning spends the principal's time twice on work
    he had already commissioned."""
    assert "a request repeated is a request already paid for" in doctrine
    assert "A REPEATED REQUEST IS A REQUEST ALREADY PAID FOR" in const


def test_THE_TIEBREAK_IS_STATED_AS_AN_IMPERATIVE(doctrine, const) -> None:
    """A principle without a tiebreak loses every close call to the cautious reading."""
    assert "BUILD, and wire it" in doctrine
    assert "between building and explaining why not: BUILD, and wire it" in const


def test_THE_LAW_KEEPS_ITS_SAFETY_EXCEPTION(const) -> None:
    """The exception is what makes the rule safe to follow at speed: faster BUILDING is aggression
    on engineering, and it never reaches sizing, the rails, or an evidence bar."""
    assert "WHAT THIS DOES NOT LICENSE" in const
    assert "survival rails" in const and "two-stage discovery law" in const
    assert "not a mandate to build the unbeneficial" in const


def test_THE_DOCTRINE_CONTAINS_NO_DEFERRAL_INSTRUCTION() -> None:
    """The generalised form: any phrase that tells an organ to postpone a build is a direct order
    to do less, regardless of the surrounding context."""
    raw = _DOCTRINE.read_text("utf-8").lower()
    for phrase in ("defer the build", "build it later", "postpone the build",
                   "leave it for a later cycle", "do not build it yet"):
        assert phrase not in raw, f"the doctrine tells an organ to defer: {phrase!r}"
