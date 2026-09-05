"""The six nested allocators: one currency, and an honest state per level.

The value of this spine is entirely in it being TRUE. A stack that reported six healthy
allocators would be worse than not having one -- the desk would stop looking for the levels that
do not exist. So what is pinned here is the honesty: a level with no decider reads UNWIRED, a
level whose ledger is absent reads WIRED not MEASURED, and every level says what is missing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.ops import allocators as al


def test_all_seven_levels_are_declared_in_dependency_order() -> None:
    """SEVEN, since the frontier allocator landed. It is level 0 rather than 7 because it FEEDS
    information: every other level spends a resource the desk already has, and this one decides
    which capability to acquire at all -- the only level whose answers come from outside."""
    assert [a.level for a in al.ALLOCATORS] == [0, 1, 2, 3, 4, 5, 6]
    assert [a.name for a in al.ALLOCATORS] == [
        "frontier", "information", "research", "compute", "forecast", "capital", "execution"]


def test_every_level_names_a_resource_a_question_and_what_prices_it() -> None:
    """A level whose resource is vague cannot be rationed: 'research quality' is not a resource."""
    for a in al.ALLOCATORS:
        assert a.question.endswith("?"), a.name
        assert a.resource and a.prices, a.name


def test_the_currency_is_named_once_and_shared() -> None:
    """Six vocabularies for one question is why a compute hour and a unit of heat could never be
    traded against each other."""
    rows = al.status()
    assert len({r["currency"] for r in rows.values()}) == 1
    assert "log W" in al.CURRENCY


def test_a_level_with_no_decider_reads_unwired(tmp_path: Path) -> None:
    """UNWIRED is not a severe WIRED. A wired level makes a decision the desk can grade later; an
    unwired one makes it anyway, by arrival order, and records nothing.

    FORECAST is that level today, and legitimately so: every predictive object on this desk is
    itself a sleeve, so `pf_allocator` already weights them and there is no second class of object
    to weight. COMPUTE held this position until its ledger landed.
    """
    rows = al.status(tmp_path)
    assert rows["forecast"]["status"] == al.UNWIRED
    assert rows["forecast"]["decides"] is None


def test_a_decider_without_its_ledger_is_wired_not_measured(tmp_path: Path) -> None:
    """On an empty tree nothing is present, so no level may claim MEASURED."""
    for name, row in al.status(tmp_path).items():
        assert row["status"] in (al.WIRED, al.UNWIRED), name
        assert row["status"] != al.MEASURED


def test_every_level_that_is_not_measured_says_what_is_missing(tmp_path: Path) -> None:
    for name, row in al.status(tmp_path).items():
        if row["status"] != al.MEASURED:
            assert row["gap"] or row["prices_missing"], f"{name} is short of MEASURED silently"


def test_a_gain_that_cannot_be_banked_is_named(tmp_path: Path) -> None:
    """'A gain at level k is worthless if k+1 cannot carry it' is not a metaphor -- it is every
    large defect this desk has measured. Research feeds compute, and compute is UNWIRED."""
    rows = al.status(tmp_path)
    assert rows["compute"]["downstream_unwired"] == ["forecast"]
    assert "cannot be banked" in rows["compute"]["carries"]


def test_the_report_names_the_weakest_link_by_level() -> None:
    """The earliest unwired level, because a break upstream makes every fix below it unbankable."""
    doc = al.report()
    assert doc["weakest_link"] == "forecast"
    assert sum(doc["counts"].values()) == 7


def test_capital_is_the_level_that_actually_works() -> None:
    """The one the desk has spent its history on -- kept as a fence so a refactor that breaks the
    allocator's own artifacts shows up here as the stack losing its only working level."""
    row = al.status()["capital"]
    assert row["decides"] == "desks/mt5/research/pf_allocator.py"
    assert row["decider_present"] is True


def test_the_rule_every_future_proposal_must_answer_is_stated() -> None:
    doc = al.report()
    assert "name the allocator it improves" in doc["rule"]
    assert "dE[log W]" in doc["rule"]


def test_writing_the_report_is_a_read_only_pass(tmp_path: Path) -> None:
    """It declares; it does not allocate. A spine that started spending things would be a seventh
    allocator nobody asked for."""
    before = al.status(tmp_path)
    assert al.status(tmp_path) == before


@pytest.mark.parametrize("name", [a.name for a in al.ALLOCATORS])
def test_no_level_claims_a_decider_file_that_does_not_exist(name: str) -> None:
    """A declared decider that is not on the tree would report WIRED for a level nothing runs --
    the exact false comfort this file exists to prevent."""
    a = al.BY_NAME[name]
    if a.decides:
        assert (al.ROOT / a.decides).exists(), f"{name} names a decider that is not here"
