"""R0602: a candidate-vs-deployed gate refuses when the book is unreadable, never admits."""
from __future__ import annotations

import pytest

from libs.research.marginal_admission import classify_book


def test_present_book_is_answerable_and_not_degenerate() -> None:
    b = classify_book(3, 3)
    assert b.state == "PRESENT"
    assert b.answerable is True and b.degenerate is False


def test_confirmed_empty_is_answerable_but_degenerate() -> None:
    """Today's real state: no book file AND the desk independently reports zero sleeves."""
    b = classify_book(None, 0)
    assert b.state == "EMPTY-CONFIRMED"
    assert b.answerable is True, "the desk must still be able to run while flat"
    assert b.degenerate is True, "the answer is standalone Sharpe, not incremental value"


def test_missing_book_while_sleeves_are_deployed_refuses() -> None:
    """THE DEFECT THIS CLOSES: absence used to degrade to the easier question for ANY reason."""
    b = classify_book(None, 2)
    assert b.state == "CONTRADICTED"
    assert b.answerable is False, "must fail toward refusing, never toward admitting"


def test_unreadable_book_refuses_and_is_distinct_from_absent() -> None:
    """L1.55: a producer that wrote garbage is not one that never ran."""
    b = classify_book(None, 0, unreadable=True)
    assert b.state == "UNREADABLE"
    assert b.answerable is False
    assert b.state != classify_book(None, 0).state, "absent and unreadable must never merge"


def test_unknown_deployed_count_refuses() -> None:
    """Unmeasured is not zero -- 'empty' cannot be CONFIRMED without the second witness."""
    b = classify_book(None, None)
    assert b.state == "UNKNOWN-DEPLOYED"
    assert b.answerable is False


def test_unreadable_outranks_every_other_signal() -> None:
    """A corrupt book must not be rescued by a healthy-looking sleeve count."""
    assert classify_book(5, 5, unreadable=True).state == "UNREADABLE"


@pytest.mark.parametrize("declared", [0, 1, 7, None])
def test_no_state_is_both_unanswerable_and_degenerate(declared: int | None) -> None:
    """`degenerate` licenses the easier question; it may never ride on a refusal."""
    for unreadable in (False, True):
        b = classify_book(None, declared, unreadable=unreadable)
        assert not (b.degenerate and not b.answerable)


def test_every_state_carries_a_reason() -> None:
    for args in [(3, 3), (None, 0), (None, 2), (None, None)]:
        assert len(classify_book(*args).why) > 25
    assert len(classify_book(None, 0, unreadable=True).why) > 25
