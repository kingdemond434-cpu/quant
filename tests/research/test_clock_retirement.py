"""The only sanctioned exit from the Holm cohort, pinned on the direction that costs money.

RETIREMENT FREES A SEAT AND MOVES NO BAR, and the test that would notice if that ever stopped
being true is `test_RETIREMENT_NEVER_LOWERS_MULTIPLICITY`. Seats are a CAPACITY limit; `m` is how
many times the desk LOOKED, and a clock that ran and failed consumed a trial that retiring it
does not un-look. Those two lived in one variable until 2026-08-14, which is the only reason
reclaiming a dead seat ever needed a human in the loop.

The rest of the value here is in the REFUSALS: an accruing clock, a clock that cannot be assessed,
a hand-typed name with no live proposal behind it. Each of those, allowed through, converts "this
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
    auto_accept,
    load,
    multiplicity_high_water,
    retired_names,
    reverse,
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
    assert row["seats_before"] == 15 and row["seats_after"] == 14
    assert row["loosens_bars"] is False and row["multiplicity_floor"] == 15, (
        "freeing a seat must never move a bar: multiplicity is a high-water mark, and the row "
        "carries it so the guarantee is auditable from the ledger alone")
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


def test_RETIREMENT_NEVER_LOWERS_MULTIPLICITY(tmp_path: Path) -> None:
    """THE PROPERTY THAT MAKES UNATTENDED RECLAMATION SAFE, and the one whose loss would be
    invisible: every bar would simply get easier and every verdict would still look well-formed.

    Retire clocks from a cohort of 15 and the high-water mark stays 15, however many are taken.
    You cannot improve a p-value by forgetting an experiment."""
    assert multiplicity_high_water(tmp_path) == 0        # nothing recorded yet
    rows, refused = auto_accept(_sweep(), decided_by="cycle", root=tmp_path)
    assert len(rows) == 2 and refused == []
    assert multiplicity_high_water(tmp_path) == 15, (
        "two seats freed from a cohort of 15 -- the seats fall, the multiplicity floor does not")


def test_AUTO_ACCEPT_TAKES_EVERY_PROPOSAL_OR_NONE(tmp_path: Path) -> None:
    """Reading the proposal list and picking the convenient entries WOULD be a judgement made
    after seeing a result the desk would rather not have. Taking all of them is not."""
    rows, _ = auto_accept(_sweep(), decided_by="cycle", root=tmp_path)
    assert {r["clock"] for r in rows} == {"trend_30d", "walcl_reserve_impulse"}
    assert all(r["decided_by"] == "cycle" for r in rows)


def test_AUTO_ACCEPT_NEVER_TOUCHES_BLOCKED_OR_ACCRUING(tmp_path: Path) -> None:
    """The asymmetry is the whole rule: wrongly reclaiming a clock that cannot be ASSESSED
    destroys forward evidence that cannot be re-earned at any price."""
    auto_accept(_sweep(), decided_by="cycle", root=tmp_path)
    retired = retired_names(tmp_path)
    assert "cashcarry" not in retired          # BLOCKED -- a measurement defect upstream
    assert "crossasset" not in retired         # ACCRUING -- doing exactly what a seat is for


def test_AUTO_ACCEPT_IS_IDEMPOTENT(tmp_path: Path) -> None:
    """It runs every cycle. A second pass over the same proposals must free nothing further and
    must not raise -- a daily organ that errored on a quiet day would be turned off within a week.
    """
    auto_accept(_sweep(), decided_by="cycle", root=tmp_path)
    rows, refused = auto_accept(_sweep(), decided_by="cycle", root=tmp_path)
    assert rows == []
    assert len(refused) == 2 and all("already retired" in r for r in refused)


def test_AN_EMPTY_SWEEP_RETIRES_NOTHING(tmp_path: Path) -> None:
    rows, refused = auto_accept({"m_now": 12, "proposals": []}, root=tmp_path)
    assert rows == [] and refused == []
    assert multiplicity_high_water(tmp_path) == 0


def test_THE_MECHANISM_OF_DEATH_IS_COPIED_NOT_INFERRED(tmp_path: Path) -> None:
    """L1.17. A refutation re-queued as untested buys the same dead axis a second time at full
    price; an instrument fault filed as refuted retires ground nobody ever measured."""
    row = accept("walcl_reserve_impulse", _sweep(), decided_by="principal", root=tmp_path)
    assert row["requeue_as"] == "UNTESTED"
    assert "instrument failed" in str(row["why"])


# ================================================== the 2026-08-14 false retirement, and its cure

def _zero_obs_sweep() -> dict[str, object]:
    """The exact proposal that cost a real clock: NO-EVIDENCE, zero observations -- published by a
    runner reading a different artifact than the collector writes."""
    return {
        "m_now": 15,
        "proposals": [{
            "clock": "perpdex_funding::aster_BTCUSDT_level_rate::8h",
            "requeue_as": "UNTESTED", "verdict": "NO-EVIDENCE", "observations": 0,
            "why": "NO-EVIDENCE with zero observations accrued -- it has spent its opportunities "
                   "and converted none of them, so there is no sample here to protect"}],
        "blocked": [], "protected": [],
    }


def test_A_ZERO_OBSERVATION_CLOCK_IS_NEVER_AUTO_RETIRED(tmp_path: Path) -> None:
    """MEASURED: this clock was auto-retired holding SEVEN forward observations on disk. Zero
    observations is the ONE verdict a broken join and a dead clock produce identically -- both are
    the absence of rows, in the same field, on the same artifact. Every other reclaimable verdict
    is computed FROM observations and cannot be manufactured by a runner that found none."""
    rows, refused = auto_accept(_zero_obs_sweep(), decided_by="cycle", root=tmp_path)
    assert rows == []
    assert len(refused) == 1 and "ZERO-OBSERVATION" in refused[0]
    assert retired_names(tmp_path) == set()


def test_A_HUMAN_MAY_STILL_RETIRE_IT_BY_HAND(tmp_path: Path) -> None:
    """The guard is on the UNATTENDED path only. Once someone has checked the join, the decision
    is theirs -- refusing it entirely would make a genuinely dead clock unretirable."""
    row = accept("perpdex_funding::aster_BTCUSDT_level_rate::8h", _zero_obs_sweep(),
                 decided_by="principal", root=tmp_path)
    assert row["clock"].startswith("perpdex_funding")


def test_A_FALSE_RETIREMENT_CAN_BE_REVERSED(tmp_path: Path) -> None:
    accept("trend_30d", _sweep(), decided_by="cycle", root=tmp_path)
    assert retired_names(tmp_path) == {"trend_30d"}

    reverse("trend_30d", why="the accrual runner read the wrong artifact",
            decided_by="principal", root=tmp_path)
    assert retired_names(tmp_path) == set(), "a reversed clock is back in the cohort"


def test_A_REVERSAL_KEEPS_THE_ROW_AS_HISTORY(tmp_path: Path) -> None:
    """Deleting the row would erase the evidence that the desk once believed the clock was dead --
    the only record that would let anyone notice the join is still broken."""
    accept("trend_30d", _sweep(), decided_by="cycle", root=tmp_path)
    reverse("trend_30d", why="false NO-EVIDENCE reading", decided_by="principal", root=tmp_path)
    rows = load(tmp_path)["retirements"]
    assert len(rows) == 1
    assert rows[0]["reversed"]["why"] == "false NO-EVIDENCE reading"
    assert rows[0]["reversed"]["by"] == "principal"


def test_A_REVERSAL_NEEDS_A_REASON_AND_A_DECIDER(tmp_path: Path) -> None:
    accept("trend_30d", _sweep(), decided_by="cycle", root=tmp_path)
    with pytest.raises(RetirementRefused, match="stated reason"):
        reverse("trend_30d", why="  ", decided_by="principal", root=tmp_path)
    with pytest.raises(RetirementRefused, match="stated reason"):
        reverse("trend_30d", why="ok", decided_by="", root=tmp_path)


def test_REVERSING_SOMETHING_NOT_RETIRED_IS_REFUSED(tmp_path: Path) -> None:
    with pytest.raises(RetirementRefused, match="not currently retired"):
        reverse("never_retired", why="x", decided_by="principal", root=tmp_path)


def test_A_REVERSED_CLOCK_CAN_BE_RETIRED_AGAIN(tmp_path: Path) -> None:
    """Reversal is not immunity. If the join is checked and the clock really is dead, it retires
    again -- and the ledger then carries both the mistake and the correction."""
    accept("trend_30d", _sweep(), decided_by="cycle", root=tmp_path)
    reverse("trend_30d", why="checking the join", decided_by="principal", root=tmp_path)
    accept("trend_30d", _sweep(), decided_by="principal", root=tmp_path)
    assert retired_names(tmp_path) == {"trend_30d"}
    assert len(load(tmp_path)["retirements"]) == 2
