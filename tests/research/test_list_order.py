"""R0457: a shuffle whose permutation is not recoverable de-biases the estimate and destroys the
residual, so the tests here are mostly about the LOG rather than about the shuffle.

The desk's pre-existing shuffle (`run_external_panel.py:538`) is unseeded and writes nothing, so
"how order-sensitive is this desk?" has been unanswerable since it shipped. These pin the property
that makes the answer cheap: every call is reconstructible from its own log row.
"""
from __future__ import annotations

import json

import pytest

from libs.research import list_order


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Never append to the live desk log from a test -- that is the L0-class defect where the
    suite writes fixture rows into a real store."""
    log = tmp_path / "list_order_log.jsonl"
    monkeypatch.setattr(list_order, "LOG", log)
    return log


def _rows(log) -> list[dict]:
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()]


def test_permutation_reconstructs_the_shown_order(_isolated_log) -> None:
    """THE LOAD-BEARING PROPERTY. A later reanalysis must be able to map an answer back to the
    POSITION it was shown in, using only the logged row."""
    items = [f"CLASS_{i}" for i in range(10)]
    shown, perm = list_order.shuffled_with_log(items, organ="t", field="f")

    row = _rows(_isolated_log)[0]
    assert [items[i] for i in row["permutation"]] == shown
    assert perm == row["permutation"]
    assert sorted(perm) == list(range(10)), "a permutation must not drop or duplicate a candidate"


def test_seed_makes_the_call_reproducible(_isolated_log) -> None:
    """The recorded seed must regenerate the exact order, or the log is a description rather than
    a reconstruction."""
    items = list("abcdefgh")
    shown, _ = list_order.shuffled_with_log(items, organ="t", field="f")
    seed = _rows(_isolated_log)[0]["seed"]

    replayed, _ = list_order.shuffled_with_log(items, organ="t", field="f", seed=seed)
    assert replayed == shown


def test_no_candidate_is_lost_or_invented(_isolated_log) -> None:
    """Ordering may change; membership may not. A shuffle that silently truncated would be a far
    worse defect than the bias it fixes."""
    items = list(range(25))
    shown, _ = list_order.shuffled_with_log(items, organ="t", field="f")
    assert sorted(shown) == items


def test_short_lists_are_still_logged(_isolated_log) -> None:
    """A one-item list carries no bias, but dropping its row would make the log's denominator the
    count of lists that happened to be long enough -- "this list was short" and "this call site
    never ran" must not read identically (L1.60)."""
    list_order.shuffled_with_log(["only"], organ="t", field="short")
    list_order.shuffled_with_log([], organ="t", field="empty")

    rows = _rows(_isolated_log)
    assert [r["n"] for r in rows] == [1, 0]
    assert [r["permutation"] for r in rows] == [[0], []]


def test_two_calls_in_the_same_instant_do_not_share_a_permutation(_isolated_log) -> None:
    """Seeding from a clock would let seats started in the same second draw the SAME order --
    correlated 'randomisation' reads as agreement and would be the bias wearing a fix's clothes."""
    items = list(range(40))
    a, _ = list_order.shuffled_with_log(items, organ="t", field="f")
    b, _ = list_order.shuffled_with_log(items, organ="t", field="f")
    assert a != b

    seeds = [r["seed"] for r in _rows(_isolated_log)]
    assert seeds[0] != seeds[1]


def test_the_wired_organs_actually_call_it(_isolated_log) -> None:
    """A helper nobody calls is unwired capability, which the desk treats as bloat. This asserts
    the two survivor-panel sites really route through the logger."""
    from libs.research import survivor_panel

    survivor_panel.round_one_prompt({"state": "x"})
    fields = {r["field"] for r in _rows(_isolated_log)}
    assert "bottleneck_classes" in fields

    survivor_panel.cross_examination_prompt({"state": "x"}, [("seat-a", "aa"), ("seat-b", "bb")])
    fields = {r["field"] for r in _rows(_isolated_log)}
    assert "round_two_seat_order" in fields
