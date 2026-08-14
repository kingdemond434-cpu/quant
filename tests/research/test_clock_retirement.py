"""The only sanctioned exit from the Holm cohort, pinned on the direction that costs money.

RETIREMENT LOOSENS EVERY REMAINING BAR. That is the phantom-edge direction, so the tests that
matter most here are the REFUSALS: an accruing clock, a clock that cannot be assessed, a
hand-typed name with no live proposal behind it. Each of those, allowed through, converts "this
clock is dead" into "this clock is inconvenient" -- and a ledger cannot tell the two apart
afterwards, which is precisely why the evidence is copied at the moment of the decision.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research.clock_retirement import (
    LEDGER,
    RetirementRefused,
    accept,
    load,
    retired_names,
)


def _sweep() -> dict[str, object]:
    return {
        "m_now": 15,
        "cap": 12,
        "proposals": [
            {"clock": "trend_30d", "kind": "standing", "requeue_as": "REFUTED",
             "verdict": "FAILING FORWARD -> kill (backtest mirage)", "evidence": "ACCRUING",
             "observations": 42, "why": "reached its own pre-registered decision point and failed"},
            {"clock": "walcl_reserve_impulse", "kind": "axis", "requeue_as": "UNTESTED",
             "verdict": "DEGENERATE", "evidence": "ACCRUING", "observations": 9,
             "why": "the instrument failed, so this clock cannot resolve however long it runs"},
        ],
        "blocked": [{"clock": "cashcarry", "why": "cannot be assessed"}],
        "protected": ["crossasset"],
    }


def test_AN_EMPTY_LEDGER_RETIRES_NOTHING(tmp_path: Path) -> None:
    assert retired_names(tmp_path) == set()
    assert load(tmp_path) == {"retirements": []}


def test_A_MALFORMED_LEDGER_RETIRES_NOTHING(tmp_path: Path) -> None:
    """The conservative direction: the cohort stays LARGER and every bar stays TIGHTER, so a
    corrupt ledger shows up as seats that will not free rather than as bars that quietly loosened.
    """
    p = tmp_path / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    for junk in ("{ not json", json.dumps([1, 2]), json.dumps({"retirements": "all of them"})):
        p.write_text(junk, "utf-8")
        assert retired_names(tmp_path) == set()


def test_ACCEPTING_A_PROPOSAL_WRITES_AN_ATTRIBUTED_EVIDENCED_ROW(tmp_path: Path) -> None:
    row = accept("trend_30d", _sweep(), decided_by="principal", root=tmp_path)

    assert row["requeue_as"] == "REFUTED"            # L1.17: retires the ground with the clock
    assert row["observations"] == 42
    assert row["decided_by"] == "principal"
    assert row["cohort_m_before"] == 15 and row["cohort_m_after"] == 14
    assert row["loosens_bars"] is True, (
        "the cost of the seat is recorded next to the decision, never left to be rediscovered")
    assert retired_names(tmp_path) == {"trend_30d"}


def test_THE_LEDGER_IS_TRACKED_NOT_RUNTIME_STATE() -> None:
    """A retirement recorded under data/ is invisible to every clone and uncitable by any audit --
    the same defect that put real trade evidence somewhere no checkout could reach (R0160)."""
    assert LEDGER.startswith("docs/"), LEDGER


def test_AN_ACCRUING_CLOCK_IS_REFUSED(tmp_path: Path) -> None:
    with pytest.raises(RetirementRefused, match="ACCRUING"):
        accept("crossasset", _sweep(), decided_by="principal", root=tmp_path)
    assert retired_names(tmp_path) == set()


def test_A_BLOCKED_CLOCK_IS_REFUSED_AND_SAYS_WHY(tmp_path: Path) -> None:
    """BLOCKED means it cannot be ASSESSED -- a measurement defect upstream. Wrongly reclaiming it
    destroys forward evidence that cannot be re-earned at any price; wrongly protecting it costs a
    queue position. Those are not comparable losses, and the asymmetry is the whole rule."""
    with pytest.raises(RetirementRefused, match="cannot be re-earned"):
        accept("cashcarry", _sweep(), decided_by="principal", root=tmp_path)


def test_A_HAND_TYPED_NAME_WITH_NO_LIVE_PROPOSAL_IS_REFUSED(tmp_path: Path) -> None:
    with pytest.raises(RetirementRefused, match="not in the current sweep"):
        accept("something_i_dislike", _sweep(), decided_by="principal", root=tmp_path)


def test_AN_UNATTRIBUTED_RETIREMENT_IS_REFUSED(tmp_path: Path) -> None:
    with pytest.raises(RetirementRefused, match="attributed decider"):
        accept("trend_30d", _sweep(), decided_by="   ", root=tmp_path)


def test_RETIRING_TWICE_IS_REFUSED(tmp_path: Path) -> None:
    accept("trend_30d", _sweep(), decided_by="principal", root=tmp_path)
    with pytest.raises(RetirementRefused, match="already retired"):
        accept("trend_30d", _sweep(), decided_by="principal", root=tmp_path)


def test_A_SECOND_RETIREMENT_APPENDS_AND_DOES_NOT_REPLACE(tmp_path: Path) -> None:
    """The ledger is a record, not a current-state file. Losing the earlier rows would lose the
    only account of why the cohort is the size it is."""
    accept("trend_30d", _sweep(), decided_by="principal", root=tmp_path)
    accept("walcl_reserve_impulse", _sweep(), decided_by="principal", root=tmp_path)
    assert retired_names(tmp_path) == {"trend_30d", "walcl_reserve_impulse"}
    assert len(load(tmp_path)["retirements"]) == 2


def test_THE_MECHANISM_OF_DEATH_IS_COPIED_NOT_INFERRED(tmp_path: Path) -> None:
    """L1.17. A refutation re-queued as untested buys the same dead axis a second time at full
    price; an instrument fault filed as refuted retires ground nobody ever measured."""
    row = accept("walcl_reserve_impulse", _sweep(), decided_by="principal", root=tmp_path)
    assert row["requeue_as"] == "UNTESTED"
    assert "instrument failed" in str(row["why"])
