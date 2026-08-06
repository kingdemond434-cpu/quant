"""THE DECLARATION THAT MAKES THE CAPACITY GATE HONEST -- 40 statements, zero tests until now.

`capacity_policy.capacity_fit` honours a DECLARED allocation, which is what admits the small edges
equal weight would exclude: a $5k edge funded with $1k is 5x headroom and perfectly safe. But a
declared number with nothing checking it is just a way to pass any capacity gate by writing a
small number. This module is the check, and until now nothing checked the check.

THREE FAILURES, DELIBERATELY KEPT APART, because collapsing any two of them loses the distinction
that makes the reconciliation worth running:

  INCONSISTENT   the declaration exceeds what the sleeve's OWN edge can hold. Refused on its face,
                 before any funding figure is consulted -- it is arithmetically impossible.
  OVERFUNDED     the sleeve is really funded above what it declared. THE BYPASS, caught.
  UNVERIFIED     there is no live funding figure to compare against. Reported, NEVER counted as
                 OK -- "nobody checked" reading as "checked and fine" is how the declaration
                 becomes decorative.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from libs.research import sleeve_allocations as SA
from libs.research.capacity_policy import max_allocation


def _alloc(sleeve: str = "s", capacity: float = 100_000.0,
           declared: float = 1_000.0) -> SA.SleeveAllocation:
    return SA.SleeveAllocation(sleeve=sleeve, capacity_usd=capacity, declared_usd=declared)


# ------------------------------------------------------------------ the ceiling

def test_the_ceiling_comes_from_the_ONE_capacity_policy() -> None:
    """Re-deriving the headroom multiple here is exactly how five disagreeing copies of the
    capacity policy appeared last time. It is imported, not restated."""
    a = _alloc(capacity=100_000.0)
    assert a.ceiling_usd == max_allocation(100_000.0)
    assert a.ceiling_usd == pytest.approx(25_000.0), "4x headroom means a QUARTER of capacity"


def test_a_declaration_at_the_ceiling_is_consistent_and_one_above_it_is_not() -> None:
    """The boundary is inclusive: filling to exactly the permitted ceiling is permitted."""
    ceiling = _alloc().ceiling_usd
    assert _alloc(declared=ceiling).self_consistent is True
    assert _alloc(declared=ceiling + 0.01).self_consistent is False


def test_a_zero_or_negative_declaration_is_NOT_consistent() -> None:
    """'I will fund it with nothing' must not be a way to clear a capacity gate -- it would make
    the required capacity collapse to the absolute floor and pass anything."""
    assert _alloc(declared=0.0).self_consistent is False
    assert _alloc(declared=-500.0).self_consistent is False


def test_a_sleeve_with_no_capacity_can_declare_nothing() -> None:
    assert _alloc(capacity=0.0, declared=1.0).self_consistent is False


def test_the_declaration_is_FROZEN_once_made() -> None:
    """A mutable declaration is not a commitment. The reconciliation compares live funding against
    what was declared when the gate was passed, so a caller that could edit it in place could pass
    the gate and then move the goalposts."""
    a = _alloc()
    with pytest.raises(ValidationError):
        a.declared_usd = 999_999.0            # type: ignore[misc]


# ------------------------------------------------------------------ loading

def _store(tmp_path: Path, payload) -> Path:
    p = tmp_path / "alloc.json"
    p.write_text(json.dumps(payload) if not isinstance(payload, str) else payload, "utf-8")
    return p


def test_a_missing_store_is_EMPTY_and_never_an_exception(tmp_path: Path) -> None:
    """This is read from inside `capacity_policy.declared_allocation`, which is itself read by
    every capacity gate on the desk. An exception here takes all of them down."""
    assert SA.load(tmp_path / "absent.json") == []


@pytest.mark.parametrize("junk", ["{not json", "[]", "null", '"a string"', "123"])
def test_a_corrupt_or_wrongly_shaped_store_is_EMPTY(tmp_path: Path, junk: str) -> None:
    assert SA.load(_store(tmp_path, junk)) == []


def test_one_malformed_row_does_not_hide_the_others(tmp_path: Path) -> None:
    """A single bad row taking the whole file down would silently disable every declaration --
    and the failure direction matters: with no declarations, equal weight applies, which is
    STRICTER. It fails safe, but it fails silently, so the partial read is the right behaviour."""
    p = _store(tmp_path, {
        "good": {"capacity_usd": 100_000.0, "declared_usd": 1_000.0},
        "missing_field": {"capacity_usd": 100_000.0},
        "not_a_number": {"capacity_usd": "lots", "declared_usd": 1_000.0},
        "also_good": {"capacity_usd": 40_000.0, "declared_usd": 500.0},
    })
    got = {a.sleeve for a in SA.load(p)}
    assert got == {"good", "also_good"}


def test_loaded_values_are_coerced_to_the_declared_types(tmp_path: Path) -> None:
    p = _store(tmp_path, {"s": {"capacity_usd": "100000", "declared_usd": "1000"}})
    a = SA.load(p)[0]
    assert isinstance(a.capacity_usd, float) and a.capacity_usd == 100_000.0


# ------------------------------------------------------------------ the three failures

def test_INCONSISTENT_is_decided_without_consulting_any_funding_figure() -> None:
    """It is arithmetically impossible on its face: the declaration exceeds what the sleeve's own
    edge can hold. Waiting for a funding number to catch it would let it pass the capacity gate in
    the meantime."""
    bad = _alloc("greedy", capacity=10_000.0, declared=9_000.0)   # ceiling is 2,500
    good = _alloc("modest", capacity=10_000.0, declared=1_000.0)
    assert SA.inconsistent([bad, good]) == [bad]


def test_OVERFUNDED_catches_the_bypass() -> None:
    """The gate was passed on a declared $1,000. Funding it with $5,000 is a breach of the
    commitment the pass was granted on, not a rounding difference."""
    a = _alloc("s", declared=1_000.0)
    out = SA.overfunded([a], {"s": 5_000.0})
    assert out == [(a, 5_000.0)]


def test_mark_to_market_drift_is_ABSORBED_so_the_check_is_not_trained_away() -> None:
    """A sleeve declared at $1,000 that marks to $1,020 has not cheated. Firing on that teaches
    the desk to ignore the check, which costs more than the 2% it would catch."""
    a = _alloc("s", declared=1_000.0)
    assert SA.overfunded([a], {"s": 1_020.0}) == []
    assert SA.overfunded([a], {"s": 1_050.0}) == [], "exactly at tolerance is still within it"
    assert SA.overfunded([a], {"s": 1_051.0}) != []


def test_the_tolerance_is_adjustable_and_a_zero_tolerance_catches_any_excess() -> None:
    a = _alloc("s", declared=1_000.0)
    assert SA.overfunded([a], {"s": 1_000.01}, tolerance=0.0) != []
    assert SA.overfunded([a], {"s": 1_000.0}, tolerance=0.0) == []


def test_an_UNDERFUNDED_sleeve_is_not_a_breach() -> None:
    """Funding below the declaration is more headroom, not less. Flagging it would push the desk
    toward filling every sleeve to its declared maximum."""
    assert SA.overfunded([_alloc("s", declared=1_000.0)], {"s": 400.0}) == []


def test_UNVERIFIED_is_reported_and_never_counted_as_OK() -> None:
    """'Nobody checked' reading as 'checked and fine' is how the declaration becomes decorative --
    and the declaration is the thing that let the small edge through the capacity gate."""
    checked = _alloc("checked")
    unchecked = _alloc("unchecked")
    funded = {"checked": 900.0}
    assert SA.unverified([checked, unchecked], funded) == [unchecked]
    assert SA.overfunded([checked, unchecked], funded) == [], (
        "an unverified sleeve must not also be reported as overfunded -- that is a different claim")


def test_an_empty_funding_map_makes_every_declaration_unverified() -> None:
    allocs = [_alloc("a"), _alloc("b")]
    assert SA.unverified(allocs, {}) == allocs
    assert SA.overfunded(allocs, {}) == []


def test_the_three_checks_are_independent_of_one_another() -> None:
    """A sleeve can be inconsistent AND overfunded AND that is two findings, not one. Collapsing
    them would let fixing the cheaper complaint hide the other."""
    bad = SA.SleeveAllocation(sleeve="s", capacity_usd=10_000.0, declared_usd=9_000.0)
    assert SA.inconsistent([bad]) == [bad]
    assert SA.overfunded([bad], {"s": 50_000.0}) == [(bad, 50_000.0)]
    assert SA.unverified([bad], {"s": 50_000.0}) == []
