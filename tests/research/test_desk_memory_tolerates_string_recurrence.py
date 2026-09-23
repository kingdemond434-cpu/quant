"""One malformed field must never take the whole corpus down -- and it did.

MEASURED 2026-09-08: `desk_memory.reach()` raised `ValueError: invalid literal for int() with
base 10: 'once, ongoing'` on L0242. `load()` called `int(row["recurrence"])` after
`_row_defects` -- which never covered that field -- so every organ's injection failed and read
NO memory, and `learn.py add` could not record a lesson about it because it loads first.
Thirty-three of 274 rows carry prose there: 'structural' (21), 'standing' (5), 'once' (3),
'once, self-inflicted', 'third time', 'second time on this desk'.

The fix coerces without inventing: digits and ordinals keep their count, 'once' is one, any
other word is the default. These tests pin that, and pin that the SHIPPED ledger loads.
"""
from __future__ import annotations

import pytest

from libs.research import desk_memory as dm


@pytest.mark.parametrize("value", [
    "once, ongoing", "structural", "once", "once, self-inflicted", "third time",
    "second time on this desk", "standing", 3, "3", 2.0, None, "", True,
])
def test_every_value_the_corpus_actually_uses_coerces_without_raising(value) -> None:
    assert isinstance(dm._recurrence(value), int)
    assert dm._recurrence(value) >= 1


def test_digits_and_ordinals_keep_their_count() -> None:
    assert dm._recurrence(3) == 3
    assert dm._recurrence("3") == 3
    assert dm._recurrence("3rd time") == 3
    assert dm._recurrence("third time") == 3
    assert dm._recurrence("second time on this desk") == 2
    assert dm._recurrence("twice") == 2
    assert dm._recurrence("once, ongoing") == 1
    assert dm._recurrence("once") == 1


def test_an_unknown_word_is_the_default_never_a_guessed_weight() -> None:
    """'structural' on 21 rows and 'standing' on 5: a guessed multiplier here would silently
    re-rank the corpus every organ is scored against."""
    assert dm._recurrence("structural") == 1
    assert dm._recurrence("standing") == 1
    assert dm._recurrence("recurring") == 1


def test_a_float_or_zero_never_produces_a_zero_count() -> None:
    """The scorer takes log2(recurrence); zero would be -inf."""
    assert dm._recurrence(0) == 1
    assert dm._recurrence(-2) == 1
    assert dm._recurrence(2.9) == 2


def test_the_shipped_ledger_loads_and_reach_does_not_raise() -> None:
    """The property that was false: the corpus as committed is readable by the injector."""
    lessons = dm.load()
    assert len(lessons) >= 270, len(lessons)
    ids = {ls.id for ls in lessons}
    assert "L0242" in ids                      # the row that took everything down
    r = dm.reach()                             # raised before the fix
    assert r is not None
