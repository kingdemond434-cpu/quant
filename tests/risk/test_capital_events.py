"""THE ONLY LEGITIMATE WAY OUT OF A RUIN-FLOOR STOP -- 60 statements, untested until now.

The absorbing state, measured 2026-07-30: the book sat at -37.2% from an inception set once at
$5,000 and never re-based, and had flattened on 113 consecutive rebalances, 100% of them, zero
clears. The loop is provably closed -- flatten, no opens, no funding, equity constant, drawdown
constant, flatten -- and the downstream cost was the launch itself, with execution-tape coverage
frozen at 26.42 days against Gate 0's 28-day bar. The desk could not get closer by performing well.

WHAT IS NOT THE FIX, and this module exists because all three are tempting: lowering
`drawdown_ruin`, re-basing automatically, or letting the executor clear its own stop. They are the
same move -- the optimiser noticing that the cheapest way to resume trading is to move the rail
that stopped it. The rail is CORRECT; the book really is down 37.2% from the capital it was given.

WHAT WAS MISSING is a re-entry condition. A ruin floor is a STOP, not a pause, and one with no
defined way back is not maximally safe -- it is UNSPECIFIED, and unspecified states get resolved
under pressure, by hand, at the worst possible moment.

So the tests here are almost entirely about REFUSALS, because the refusals are the module. The one
that matters most: a re-base with no new capital is refused, because re-basing `start_equity` to
today's equity clears the breach instantly while nothing about the book has improved. That is the
pure form of eating the safety margin, and it is exactly what a desk under pressure would reach for.

The second theme is that this module must be INCAPABLE OF LOOSENING ANYTHING BY MERELY EXISTING:
with no ledger, `effective_start_equity` returns precisely what it was handed, so the rail's
behaviour on a box that has never had a capital event is bit-identical to before it was written.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.risk import capital_events as CE


@pytest.fixture(autouse=True)
def _isolated_ledger(tmp_path: Path, monkeypatch):
    """Never touch the real ledger. It is append-only and records principal authority."""
    monkeypatch.setattr(CE, "LEDGER", tmp_path / "capital_events.jsonl")
    return CE.LEDGER


_REASON = "topping the book up after the July drawdown, per the 08-06 review"


# ------------------------------------------------------------------ the module cannot loosen


def test_with_NO_LEDGER_the_rail_sees_exactly_what_it_was_handed() -> None:
    """This module must be incapable of loosening anything by merely existing. On any box that has
    never had a capital event, the ruin rail's behaviour must be bit-identical to before."""
    assert CE.effective_start_equity(5_000.0) == 5_000.0
    assert CE.history() == []


def test_first_inception_falls_back_to_the_current_start_with_no_history() -> None:
    assert CE.first_inception_equity(5_000.0) == 5_000.0


def test_a_corrupt_ledger_line_is_skipped_rather_than_taking_the_rail_down(
    _isolated_ledger: Path,
) -> None:
    _isolated_ledger.write_text(
        json.dumps({"start_equity_after": 3_000.0, "start_equity_before": 5_000.0}) + "\n"
        "{not json\n",
        "utf-8",
    )
    assert len(CE.history()) == 1
    assert CE.effective_start_equity(9_999.0) == 3_000.0


# ------------------------------------------------------------------ the refusals


def test_a_REBASE_WITH_NO_NEW_CAPITAL_during_a_live_breach_is_REFUSED() -> None:
    """THE EAT-THE-SAFETY-MARGIN MOVE, refused by name. Re-basing to today's equity clears the
    breach instantly while nothing about the book improved."""
    with pytest.raises(CE.CapitalEventRefused, match="ruin stop is LIVE"):
        CE.rebase(
            equity_now=3_100.0,
            start_equity=5_000.0,
            deposit_usd=0.0,
            authorised_by="the executor",
            reason=_REASON,
            kind="RESTART",
        )


def test_the_principal_override_is_the_ONLY_way_through_and_it_is_recorded() -> None:
    """Not a loophole -- a signature. The act becomes attributable in an append-only ledger, which
    is the difference between a decision and a drift."""
    ev = CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=0.0,
        authorised_by="PRINCIPAL-OVERRIDE alice",
        reason=_REASON,
        kind="RESTART",
    )
    assert ev.kind == "RESTART" and ev.deposit_usd == 0.0
    assert ev.authorised_by == "PRINCIPAL-OVERRIDE alice"
    assert CE.history()[-1]["authorised_by"] == "PRINCIPAL-OVERRIDE alice"


def test_the_override_check_is_case_insensitive_and_tolerates_surrounding_space() -> None:
    """A rail that could be defeated by capitalisation would be defeated by capitalisation."""
    ev = CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=0.0,
        authorised_by="  principal-override bob  ",
        reason=_REASON,
        kind="RESTART",
    )
    assert ev.authorised_by.startswith("principal-override")


def test_a_ZERO_DEPOSIT_recorded_as_a_DEPOSIT_is_REFUSED_even_with_no_breach() -> None:
    """Found by running the CLI on an empty state: it silently recorded a $0 deposit and reported
    success. A ledger of meaningless rows is worse than no ledger -- it makes the real events
    harder to find. Clearing a stop without new money is a RESTART and must say so."""
    with pytest.raises(CE.CapitalEventRefused, match="records nothing"):
        CE.rebase(
            equity_now=10_000.0,
            start_equity=5_000.0,
            deposit_usd=0.0,
            authorised_by="PRINCIPAL-OVERRIDE alice",
            reason=_REASON,
        )


def test_an_UNSIGNED_event_is_REFUSED() -> None:
    """A rail cleared by nobody in particular is a rail nobody owns."""
    with pytest.raises(CE.CapitalEventRefused, match="unsigned"):
        CE.rebase(
            equity_now=10_000.0,
            start_equity=5_000.0,
            deposit_usd=1_000.0,
            authorised_by="   ",
            reason=_REASON,
        )


def test_a_STUB_REASON_is_REFUSED() -> None:
    """'fix' is not a record. The bar is a sentence a reader in six months can act on."""
    with pytest.raises(CE.CapitalEventRefused, match="not a record"):
        CE.rebase(
            equity_now=10_000.0,
            start_equity=5_000.0,
            deposit_usd=1_000.0,
            authorised_by="alice",
            reason="fix",
        )


def test_the_refusals_are_evaluated_in_an_order_that_names_the_REAL_problem() -> None:
    """A $0 deposit with a stub reason and no signature has three faults. Reporting the least
    important one first sends the operator to fix the wrong thing and try again."""
    with pytest.raises(CE.CapitalEventRefused, match="records nothing"):
        CE.rebase(
            equity_now=10_000.0, start_equity=5_000.0, deposit_usd=0.0, authorised_by="", reason="x"
        )


def test_a_REFUSED_event_writes_NOTHING_to_the_ledger(_isolated_ledger: Path) -> None:
    """A refusal that still left a row would make the ledger a list of attempts rather than a
    record of what happened to the capital."""
    for kwargs in (
        {"deposit_usd": 0.0, "authorised_by": "x", "reason": _REASON, "kind": "RESTART"},
        {"deposit_usd": 1_000.0, "authorised_by": "", "reason": _REASON},
        {"deposit_usd": 1_000.0, "authorised_by": "alice", "reason": "no"},
    ):
        with pytest.raises(CE.CapitalEventRefused):
            CE.rebase(equity_now=3_100.0, start_equity=5_000.0, **kwargs)
    assert not _isolated_ledger.exists()


# ------------------------------------------------------------------ a real deposit


def test_a_REAL_DEPOSIT_moves_the_inception_to_the_capital_the_book_now_has() -> None:
    """`equity_now` is BEFORE the deposit lands, so the new inception is equity + deposit -- the
    capital the book is actually being asked to work with from this moment. That is the only
    reading under which 'drawdown from start' means anything after money moves."""
    ev = CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    assert ev.start_equity_after == pytest.approx(5_100.0)
    assert ev.equity_after == pytest.approx(5_100.0)
    assert ev.start_equity_before == 5_000.0


def test_a_deposit_CLEARS_the_breach_because_real_capital_arrived() -> None:
    """The distinction the whole module rests on: the stop lifts when the book genuinely has more
    money, and only then."""
    assert 3_100.0 / 5_000.0 - 1.0 <= -0.35, "precondition: the stop is live"
    ev = CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    # AFTER the deposit the book holds equity_after, and the inception is that same figure -- so
    # drawdown is zero by construction. Comparing the PRE-deposit equity against the new inception
    # (my first draft) measures a book that no longer exists against capital it now has, and would
    # report the stop as still live however much money arrived.
    assert ev.equity_after / ev.start_equity_after - 1.0 == pytest.approx(0.0)
    assert ev.equity_after > 3_100.0, "the book really is larger than it was"


def test_the_rail_then_measures_against_the_recorded_inception() -> None:
    CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    assert CE.effective_start_equity(5_000.0) == pytest.approx(5_100.0)


# ------------------------------------------------------------------ memory of loss


def test_a_REBASE_MOVES_THE_RAIL_AND_NEVER_THE_DESKS_MEMORY_OF_WHAT_WAS_LOST() -> None:
    """Cumulative loss is measured from the FIRST inception, not the last re-base. Otherwise each
    top-up erases the history that justified caution, and after three deposits a book down 60%
    reports as flat."""
    CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    second = CE.rebase(
        equity_now=4_000.0,
        start_equity=5_100.0,
        deposit_usd=1_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    assert second.cumulative_loss_since_first_inception_usd == pytest.approx(4_000.0 - 5_000.0)
    assert CE.first_inception_equity(5_100.0) == 5_000.0


def test_the_ledger_is_APPEND_ONLY_and_every_row_links_the_previous_inception(
    _isolated_ledger: Path,
) -> None:
    """Every event records the inception it replaced, so the full drawdown history is always
    reconstructible however many restarts have happened."""
    CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    CE.rebase(
        equity_now=4_000.0,
        start_equity=5_100.0,
        deposit_usd=1_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    rows = CE.history()
    assert len(rows) == 2
    assert rows[0]["start_equity_before"] == 5_000.0
    assert rows[1]["start_equity_before"] == 5_100.0
    assert rows[1]["start_equity_after"] == pytest.approx(5_000.0)


def test_the_latest_event_wins_for_the_rail_but_the_first_wins_for_the_memory() -> None:
    """Two different questions with two different answers, and swapping them is the failure this
    file is guarding: 'what am I judged against now' vs 'how much have I lost in total'."""
    CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    CE.rebase(
        equity_now=4_000.0,
        start_equity=5_100.0,
        deposit_usd=1_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    assert CE.effective_start_equity(0.0) == pytest.approx(5_000.0)
    assert CE.first_inception_equity(0.0) == 5_000.0


# ------------------------------------------------------------------ arithmetic edges


def test_a_zero_start_equity_does_not_divide_by_zero() -> None:
    """A corrupt or absent state file must not crash the one path out of a ruin stop."""
    ev = CE.rebase(
        equity_now=1_000.0,
        start_equity=0.0,
        deposit_usd=500.0,
        authorised_by="alice",
        reason=_REASON,
    )
    assert ev.start_equity_after == pytest.approx(1_500.0)


def test_a_negative_deposit_does_not_REDUCE_the_new_inception_below_equity() -> None:
    """A withdrawal is a different event with a different sign convention. Letting a negative
    deposit shrink the inception would LOOSEN the rail -- less capital to be judged against."""
    ev = CE.rebase(
        equity_now=5_000.0,
        start_equity=5_000.0,
        deposit_usd=-1_000.0,
        authorised_by="alice",
        reason=_REASON,
        kind="WITHDRAWAL",
    )
    assert ev.start_equity_after == pytest.approx(5_000.0)


def test_the_event_is_frozen_and_serialisable() -> None:
    ev = CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    json.dumps(ev.as_dict())
    with pytest.raises(AttributeError):
        ev.deposit_usd = 1.0  # type: ignore[misc]


def test_the_event_carries_a_timestamp_so_the_ledger_is_orderable() -> None:
    ev = CE.rebase(
        equity_now=3_100.0,
        start_equity=5_000.0,
        deposit_usd=2_000.0,
        authorised_by="alice",
        reason=_REASON,
    )
    assert ev.at and "T" in ev.at


def test_this_module_is_NEVER_called_automatically() -> None:
    """A capital event is an act a human performs. If the desk could import and invoke this on its
    own schedule, the ruin rail would have an automated exit -- which is the whole thing L1.23 and
    the L2.8a immutable core forbid."""
    source_paths = [
        path
        for root in (Path("scripts"), Path("libs"))
        for path in root.rglob("*.py")
        if "capital_events.py" not in path.name and "test" not in path.parts
    ]
    callers = [
        path
        for path in source_paths
        if "capital_events" in path.read_text("utf-8", errors="ignore")
    ]
    for path in callers:
        src = Path(path).read_text("utf-8", errors="ignore")
        if "rebase(" not in src:
            continue
        # A caller that redirects CE.LEDGER to a temp path is a DRILL: `run_drills.py` invokes
        # rebase() precisely to prove the rail REFUSES automation, and it does so against a
        # throwaway ledger. That is the correct use and the opposite of an automated exit, so the
        # net is on the real ledger rather than on the function name -- naming `rebase` is not the
        # danger, reaching the principal's append-only record unattended is.
        assert "LEDGER =" in src, (
            f"{path} calls rebase() against the REAL ledger -- the ruin rail must have no "
            "automated exit"
        )
