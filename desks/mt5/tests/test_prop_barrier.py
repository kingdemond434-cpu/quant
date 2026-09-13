"""The E8 Pro simulator, pinned on the properties that make its answer worth reading.

Every one of these was a real failure mode of the file rather than a property invented after it
worked -- the first version of `prop_barrier` reported a 98% pass rate on a book with NO EDGE,
and the tests below are what that was traded for.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import prop_barrier as pb  # noqa: E402


def _book(**over: object) -> pb.Book:
    kw: dict = {"sleeves": 4, "risk_frac": 0.005, "exp_r": 0.10, "rr": 1.5,
                "trades_per_day_per_sleeve": 0.64, "rho": 0.70}
    kw.update(over)
    return pb.Book(**kw)


def test_the_speed_floor_is_derived_from_the_rules_and_not_asserted() -> None:
    """The 2% daily cap strips excess at rollover, so target/2% is a wall no book can climb.

    Five days for this account's 10% target. If this number is ever computed from a strategy's
    firing rate rather than from the rules, the file has started answering the wrong question.
    """
    assert pb.min_days(0.10) == 5
    assert pb.min_days(0.08) == 4
    assert pb.TARGET == 0.10, "the principal read 10% off the dashboard 2026-09-12"


def test_a_driftless_book_is_not_rescued_by_a_daily_stop() -> None:
    """THE BUG THIS FILE EXISTS TO HAVE CAUGHT ONCE.

    A stop applied to a walk with no drift, whose right tail is confiscated by the profit cap,
    cannot manufacture an edge -- it moves variance, not drift. The first version drew one common
    factor per DAY, so the first trade of a day revealed the whole day's regime and "stop after
    one loss" became a regime detector: it reported 98% on exactly this book. The correlation is
    now per SESSION, because the same sleeve at 03:00 and at 14:00 is not the same bet.

    The bound is deliberately loose. The claim is not "the stop is worthless on a driftless book",
    it is "the stop cannot turn a coin flip into a certainty", and a test that pinned a tight
    number would fail on a seed change while catching nothing.
    """
    b = _book(exp_r=0.0)
    without = pb.simulate(b, 0.10, n_paths=4_000).summary()["p_pass"]
    withstop = pb.simulate(b, 0.10, n_paths=4_000, stand_down=0.0035).summary()["p_pass"]
    assert without < 0.5, "a driftless book must not pass a 1:1 barrier more than half the time"
    assert withstop < 0.5, (
        f"a daily stop raised a NO-EDGE book to {withstop:.3f}; that is the daily-common-factor "
        "bug returning, not a strategy")


def test_a_stop_cannot_help_a_book_that_fires_all_at_once() -> None:
    """THE SECOND TIME THIS FILE FAKED AN EDGE, and the fault had moved.

    The first version drew one correlation factor per DAY, so the first trade revealed the day's
    regime. That was fixed by splitting the day into sessions. This one survived the fix: the
    halt was evaluated on RUNNING equity between sequential trades, which models a book that
    trickles in over the day and can stand down partway.

    The desk's certified book is entirely in the asia window -- all twenty sleeves fire together.
    By the time the first loss exists the other nineteen are already open, and no rule can stop
    them. A voluntary stop can only refuse to OPEN something; it cannot un-take a simultaneous
    trade. Modelled wrongly it turned the first trade into a regime detector and reported a
    NO-EDGE book passing 98.5% against 2.9% without the rule.

    The bound is loose on purpose: the claim is not "a stop is worth exactly nothing here", it is
    "a stop cannot turn a coin flip into a certainty".
    """
    b = pb.Book(sleeves=20, rho=0.66, risk_frac=0.0015, exp_r=0.0, rr=1.5,
                trades_per_day_per_sleeve=1.0, sessions=1)
    without = pb.simulate(b, 0.10, n_paths=4_000).summary()["p_pass"]
    withstop = pb.simulate(b, 0.10, n_paths=4_000, stand_down=0.0075).summary()["p_pass"]
    assert withstop < 0.5, (
        f"a stand-down raised a simultaneous NO-EDGE book to {withstop:.3f}; a stop that cannot "
        "refuse anything cannot add drift")
    assert withstop < without + 0.25, (
        f"{without:.3f} -> {withstop:.3f} is too large a move for a rule with nothing to refuse")


def test_the_day_is_several_independent_sessions() -> None:
    """The structural fact the fix rests on, pinned so it cannot be quietly set to 1."""
    assert _book().sessions >= 3


def test_the_profit_cap_actually_strips() -> None:
    """A book big enough to clear +2% in a day must be seen to lose the excess.

    If this is zero the cap is not wired, and every pass time in the file is optimistic.
    """
    s = pb.simulate(_book(risk_frac=0.01, exp_r=0.30), 0.10, n_paths=4_000).summary()
    assert s["profit_stripped_median_usd"] > 0


def test_the_daily_floor_is_what_kills_a_large_book_not_the_static_one() -> None:
    """The finding that inverts the usual prop posture, and the reason the stand-down exists.

    At size, the 2.5% daily floor is reached long before the 10% static floor -- so the thing to
    manage on this account is daily variance, not total drawdown.
    """
    s = pb.simulate(_book(risk_frac=0.0075), 0.10, n_paths=4_000).summary()
    assert s["p_fail_daily"] > 5 * s["p_fail_static"]


def test_a_voluntary_stand_down_nearly_removes_daily_breaches_but_cannot_remove_them_all() -> None:
    """What the rule is actually for -- and the honest limit of it.

    The stand-down sits INSIDE E8's own floor, so it takes the firm's wall off the board for any
    path that reaches it BETWEEN entries. It cannot take it off entirely, and this test said it
    could until the simultaneous-firing fix: a stop can only refuse to OPEN something, so trades
    already on when the session began can still carry equity through the floor together. The
    residual is small and it is real, and a test asserting exactly zero was asserting that a
    stand-down could close a position, which it cannot.

    The failures it DOES prevent move to the static floor and to timeouts, which is where a
    variance reduction should send them.
    """
    b = _book(risk_frac=0.0075)
    without = pb.simulate(b, 0.10, n_paths=4_000).summary()["p_fail_daily"]
    withstop = pb.simulate(b, 0.10, n_paths=4_000, stand_down=0.0050).summary()["p_fail_daily"]
    assert withstop < without / 10, (
        f"the stand-down must take most of the wall away: {without} -> {withstop}")
    assert withstop < 0.05


def test_the_win_rate_reconstructs_the_declared_expectancy() -> None:
    """p*rr - (1-p) == exp_r, because the barrier cares about the shape and not only the mean."""
    for exp_r in (0.0, 0.10, 0.30):
        for rr in (1.0, 1.5, 2.5):
            b = _book(exp_r=exp_r, rr=rr)
            assert abs(b.win_rate * rr - (1.0 - b.win_rate) - exp_r) < 1e-9


def test_smaller_is_not_always_better_on_this_account() -> None:
    """THE SHAPE THAT MAKES THIS ACCOUNT DIFFERENT FROM THE DYNAMIC-DRAWDOWN ONE.

    On E8 One's trailing drawdown the answer was monotone -- smaller always raised P(pass) and
    only cost time. The 2% profit cap puts a floor under how slow a book may be, so the optimum
    here is INTERIOR: 0.35% beats both 0.15% (which times out) and 0.75% (which breaches). A file
    that recommended "as small as the time budget tolerates" would be wrong on this account.
    """
    p = {r: pb.simulate(_book(risk_frac=r), 0.10, n_paths=6_000).summary()["p_pass"]
         for r in (0.0015, 0.0035, 0.0075)}
    assert p[0.0035] > p[0.0015], f"too small times out: {p}"
    assert p[0.0035] > p[0.0075], f"too large breaches: {p}"
