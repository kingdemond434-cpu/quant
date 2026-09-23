"""The macro interrupt is priced by the allocator, not by None.

THE STATE THIS REPLACES. `run_macro_intel` called the interrupt gate with:

    expected_gain_per_day=None, expected_turnover=0.0
    # The allocator prices the move, not this layer. None until the hook is landed.

`should_fire` reads a None gain as "cannot show the move beats its own cost" and returns HOLD. So
every interrupt decision this layer ever made died at that one gate, whatever the event was: the
package could observe, classify, credit, price surprise, replay and REQUEST an interrupt, and
could never actually get one. The macro brain was wired to the allocator through a constant.

NOTHING IS ESTIMATED HERE. Both numbers already existed inside the allocator's own solve --
`gain = book.mean_log_growth - held["mean_log_growth"]`, the gap between what the new solve is
worth and what the desk is actually HOLDING, and the turnover the move would cause -- and only the
gain had no publisher. `pf_allocator` now writes `no_trade.gain_per_day` and this module reads it.

WHAT THESE TESTS PIN is the fail-closed half, because that is the half that spends money: an
absent, unreadable, stale, non-finite or non-numeric solve must produce None WITH A REASON, and
None is HOLD. A stale price is worse than no price for a layer whose whole case is that
information decays faster than the allocator's own clock.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ap = pytest.importorskip("macro.allocator_price")
it = pytest.importorskip("macro.interrupt")


def _solve(tmp_path: Path, *, gain, turnover=0.02, age_s: float = 0.0, block=True) -> Path:
    doc: dict = {"at": "2026-09-05T20:00:00+00:00"}
    if block:
        doc["no_trade"] = {"verdict": "REBALANCE", "turnover": turnover, "gain_per_day": gain}
    path = tmp_path / "pf_allocation.json"
    path.write_text(json.dumps(doc), "utf-8")
    if age_s:
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
    return path


class TestThePriceComesFromTheAllocator:
    def test_a_fresh_solve_gives_the_gain_and_the_turnover(self, tmp_path) -> None:
        gain, turnover, why = ap.price_the_move(_solve(tmp_path, gain=0.0031, turnover=0.042))
        assert gain == pytest.approx(0.0031)
        assert turnover == pytest.approx(0.042)
        assert "log-wealth/day" in why

    def test_a_negative_gain_is_carried_through_rather_than_clamped(self, tmp_path) -> None:
        """A solve worth LESS than the held book is a real answer and the gate must see it: it
        makes `gain_at_risk` negative, so the interrupt correctly refuses. Clamping at zero here
        would hide the case where re-solving is actively worse."""
        gain, _, _ = ap.price_the_move(_solve(tmp_path, gain=-0.004))
        assert gain == pytest.approx(-0.004)

    def test_a_missing_turnover_reads_as_no_movement_not_as_a_refusal(self, tmp_path) -> None:
        path = tmp_path / "pf_allocation.json"
        path.write_text(json.dumps({"no_trade": {"gain_per_day": 0.002}}), "utf-8")
        gain, turnover, _ = ap.price_the_move(path)
        assert gain == pytest.approx(0.002) and turnover == 0.0


class TestItFailsClosedAndSaysWhy:
    def test_no_solve_at_all(self, tmp_path) -> None:
        gain, turnover, why = ap.price_the_move(tmp_path / "nothing.json")
        assert gain is None and turnover == 0.0
        assert "nothing has priced a move" in why

    def test_an_unreadable_solve(self, tmp_path) -> None:
        path = tmp_path / "pf_allocation.json"
        path.write_text("{not json", "utf-8")
        gain, _, why = ap.price_the_move(path)
        assert gain is None and "unreadable" in why

    def test_a_solve_with_no_no_trade_block(self, tmp_path) -> None:
        gain, _, why = ap.price_the_move(_solve(tmp_path, gain=0.1, block=False))
        assert gain is None and "never priced" in why

    def test_a_stale_solve_is_refused_by_age(self, tmp_path) -> None:
        """The allocator's NORMAL pass -- the one that writes this block -- runs every 15 minutes,
        so the tolerance is two of those. Past it the file prices a book the desk may no longer
        hold, and acting on it is worse than not acting."""
        old = ap.ALLOCATOR_NORMAL_PERIOD_S * 2 + 60
        gain, _, why = ap.price_the_move(_solve(tmp_path, gain=0.9, age_s=old))
        assert gain is None and "old" in why

    def test_a_solve_just_inside_the_window_is_still_a_price(self, tmp_path) -> None:
        """A tolerance below one allocator period would call every price stale, including a
        perfectly current one read seconds before the next pass."""
        fresh = ap.ALLOCATOR_NORMAL_PERIOD_S * 2 - 120
        gain, _, _ = ap.price_the_move(_solve(tmp_path, gain=0.9, age_s=fresh))
        assert gain == pytest.approx(0.9)

    def test_a_null_gain_is_the_ruinous_book_case_and_is_named(self, tmp_path) -> None:
        """`pf_allocator` publishes None when the held book has no finite growth rate to improve
        on. That is the right answer for the no-trade filter (move off it) and an unusable one for
        an economic gate comparing a gain to a cost, so it becomes HOLD and the fast clock keeps
        the case -- never an infinity that fires every interrupt."""
        gain, _, why = ap.price_the_move(_solve(tmp_path, gain=None))
        assert gain is None and "no growth rate to improve on" in why

    def test_a_non_numeric_gain(self, tmp_path) -> None:
        gain, _, why = ap.price_the_move(_solve(tmp_path, gain="lots"))
        assert gain is None and "not numeric" in why

    def test_an_infinite_gain_never_reaches_the_gate(self, tmp_path) -> None:
        gain, _, why = ap.price_the_move(_solve(tmp_path, gain=float("inf")))
        assert gain is None and "not finite" in why


class TestTheGateActuallyMoves:
    """The point of the hook: a decision that previously could only be HOLD can now be either."""

    _EVENT = dict(importance=0.9, importance_status=it.Status.MEASURED, unpriced_fraction=0.8,
                  decay_half_life_s=10.0, capital_authority=True, history=(), now=1.0)

    def test_a_priced_move_can_now_fire(self, tmp_path) -> None:
        gain, turnover, _ = ap.price_the_move(_solve(tmp_path, gain=5.0, turnover=0.001))
        d = it.should_fire(**self._EVENT, expected_gain_per_day=gain,
                           expected_turnover=turnover)
        assert d.fire is True, d.reason

    def test_the_same_event_with_an_unpriced_move_still_holds(self, tmp_path) -> None:
        gain, turnover, _ = ap.price_the_move(tmp_path / "absent.json")
        d = it.should_fire(**self._EVENT, expected_gain_per_day=gain,
                           expected_turnover=turnover)
        assert d.fire is False
        assert "not priced by the allocator" in d.reason

    def test_a_move_that_costs_more_than_it_buys_is_refused_on_the_arithmetic(self,
                                                                             tmp_path) -> None:
        """Not on a missing number -- on the economics, which is what the gate is for."""
        gain, turnover, _ = ap.price_the_move(_solve(tmp_path, gain=1e-6, turnover=0.5))
        d = it.should_fire(**self._EVENT, expected_gain_per_day=gain,
                           expected_turnover=turnover)
        assert d.fire is False and "turnover" in d.reason


def test_the_runner_no_longer_hardcodes_none() -> None:
    """A source fence, deliberately: the defect was a LITERAL in the call, and a literal is what
    could come back. The behaviour above cannot see `run_macro_intel`'s own call site.

    ASKED OF THE CODE, NOT THE FILE. The comment recording the defect necessarily contains the
    defect's text, so matching the raw source finds the explanation and calls it the bug -- which
    would either fail forever or force the history to be deleted to make a test pass.
    """
    src = (_DESK / "macro" / "run_macro_intel.py").read_text("utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "expected_gain_per_day=None" not in code
    assert "allocator_price.price_the_move()" in code


def test_the_allocator_publishes_the_number_this_reads() -> None:
    """The two halves of the hook are in different files and only fail together at runtime; this
    is what catches the publisher being removed."""
    src = (_DESK / "research" / "pf_allocator.py").read_text("utf-8")
    assert 'nt["gain_per_day"]' in src
