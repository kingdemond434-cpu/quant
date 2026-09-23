"""A forward clock may only exist on a symbol this desk is allowed to hypothesise about.

MEASURED ON THE LIVE BOARD 2026-09-08. Of 27 forward clocks, 10 read BLOCKED_NO_BARS -- and
EIGHT of those are AFG and AFL, registry rows carrying `asset_class: None` and `bars: None`.
`universe_policy.lane` calls them UNCLASSIFIED, so `may_hypothesise` is False and the desk may
not seek a statistical edge in them at all. They should never have been enrolled.

WHY THE WRONG STATUS WAS THE EXPENSIVE PART. BLOCKED_NO_BARS tells an operator to subscribe the
symbol in Market Watch and backfill its history. For an instrument the policy excludes that is
real work buying exactly nothing -- and worse, it succeeds: the row then goes ACTIVE and starts
accruing evidence toward a promotion the mandate forbids. Eight "backfill these" items become one
"these should not exist".

THIS ALSO ENFORCES THE PRINCIPAL'S OWN STANDING INSTRUCTION, which the policy already encoded and
the enroller was not consulting: "hypothesis fr single stocks like apple as example shouldnt be
reseaarched theyre traded purely randomly based on macro and data n instant news exploiting"
(2026-09-06). Apple and Tesla resolve to the EVENT lane and are refused here for the same reason.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from universe_policy import lane, may_hypothesise  # noqa: E402

SRC = (_DESK / "research" / "shadow_forward.py").read_text("utf-8")


def test_the_excluded_symbols_that_actually_hold_clocks_are_excluded() -> None:
    """AFG and AFL are the eight blocked clocks on the live board."""
    for sym in ("AFG", "AFL"):
        assert not may_hypothesise(sym), sym
        assert lane(sym) == "unclassified", sym


def test_single_name_equities_are_refused_by_the_lane_the_principal_asked_for() -> None:
    for sym in ("Apple", "Tesla", "Microsoft", "Amazon"):
        assert not may_hypothesise(sym), sym
        assert lane(sym) == "event", sym


def test_the_desk_s_real_book_is_still_allowed() -> None:
    """The guard must not touch what the desk actually trades."""
    for sym in ("EURUSD", "XAUUSD", "USDJPY", "GBPJPY", "CADJPY", "EURJPY"):
        assert may_hypothesise(sym), sym


def test_the_enroller_checks_the_policy_BEFORE_it_fetches_bars() -> None:
    """Order matters: reaching the bars branch first labels the row BLOCKED_NO_BARS and sends the
    operator to do work that cannot help."""
    i_policy = SRC.index("REFUSED_BY_UNIVERSE_POLICY")
    i_bars = SRC.index('st["status"] = "BLOCKED_NO_BARS"')
    assert i_policy < i_bars, "the policy refusal must precede the no-bars branch"


def test_the_refusal_revokes_both_authorities() -> None:
    block = SRC[SRC.index('st["status"] = "REFUSED_BY_UNIVERSE_POLICY"'):][:1400]
    assert 'st["promotion_authority"] = False' in block
    assert 'st["order_authority"] = False' in block


def test_the_refusal_is_terminal_so_a_later_pass_cannot_quietly_reopen_it() -> None:
    from research import shadow_forward
    assert "REFUSED_BY_UNIVERSE_POLICY" in shadow_forward._TERMINAL_STATUSES
    assert shadow_forward._is_terminal("REFUSED_BY_UNIVERSE_POLICY")


def test_the_reason_names_the_right_cure() -> None:
    """A refusal that sends somebody to backfill bars is the defect this replaces."""
    block = SRC[SRC.index('st["status"] = "REFUSED_BY_UNIVERSE_POLICY"'):][:1800]
    assert "NOT to" in block and "backfill" in block
    assert "stop certifying it" in block


def test_a_missing_policy_module_enrols_exactly_as_before() -> None:
    """`shadow_forward` runs on the trading box and must not acquire a hard dependency: no policy
    module means the old behaviour, not a refused book."""
    block = SRC[SRC.index("from universe_policy import"):][:400]
    assert "_allowed, _lane = True" in block
