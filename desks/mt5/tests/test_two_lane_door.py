"""The two-lane mandate is enforced at the DOCKET's door, not only the backtest's.

THE PRINCIPAL, 2026-09-06: single-name equities are traded on news, financial reports and
earnings reaction -- never hunted for statistical hypotheses. Routing was wired at
`run_external_backtest.route_by_lane`, which is the BACKTEST's door; nothing stood at the
docket's.

MEASURED 2026-09-12 by `frontier_map`: 10,927 of 21,582 docket cells -- 51% -- sat on symbols
`may_hypothesise` returns False for, holding ZERO certificates between them at a 0.046% upper
bound, and 447 of them were first seen in September, AFTER the mandate. The leak was live.

WHY A TEST AND NOT JUST A FIX. Trial count is a shared cost: every equity cell raised the bar
every FX and metals cell had to clear, so this door is worth more to the desk's growth than most
things it could gate. A door with no test is a door that reopens the next time someone edits the
donation path, and nothing would say so -- the docket would simply start filling again.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.proposer_common import _lane_filtered  # noqa: E402


def test_hypothesis_lane_symbols_are_admitted() -> None:
    """Gold and FX are the hypothesis lane and must pass untouched."""
    ok, refused = _lane_filtered([{"symbol": "XAUUSD", "family": "session_range_breakout"},
                                  {"symbol": "EURUSD", "family": "momentum_volgate"}])
    assert [c["symbol"] for c in ok] == ["XAUUSD", "EURUSD"]
    assert refused == []


def test_single_name_equities_are_refused_with_a_reason() -> None:
    """An equity hypothesis is turned away AND says why -- a silent drop is not a refusal."""
    ok, refused = _lane_filtered([{"symbol": "Apple", "family": "discovered"},
                                  {"symbol": "GoldmanSachs", "family": "discovered"}])
    assert ok == []
    assert {r["symbol"] for r in refused} == {"Apple", "GoldmanSachs"}
    for r in refused:
        assert "two-lane mandate" in r["why"]


def test_a_row_with_no_symbol_is_not_refused() -> None:
    """ABSENCE IS NOT A VERDICT (L1.28a). A row that names no instrument has not been shown to
    be in the wrong lane, and refusing it would turn a missing field into a policy breach."""
    ok, refused = _lane_filtered([{"family": "macro_conditional"}])
    assert len(ok) == 1
    assert refused == []


def test_the_filter_never_takes_the_intake_dark() -> None:
    """A mixed batch loses only the wrong-lane rows; the rest still reach the docket."""
    ok, refused = _lane_filtered([{"symbol": "XAUUSD", "family": "f"},
                                  {"symbol": "Apple", "family": "f"},
                                  {"symbol": "GBPUSD", "family": "f"}])
    assert [c["symbol"] for c in ok] == ["XAUUSD", "GBPUSD"]
    assert len(refused) == 1


# ------------------------------------------------------------------ THE DOCKET'S LAST FUNNEL
# THE DOOR THE MANDATE STILL LEAKED THROUGH (measured 2026-09-24). `_lane_filtered` above stands
# at the DONATION door and `route_by_lane` at the BACKTEST's -- but `merge_hypotheses` is the one
# funnel EVERY producer flows through, and its bank loop re-admits every row ever minted on every
# hourly run. So the residue banked before the two-lane order was re-minted into the judge's
# docket hour after hour: 932 rows across 103 single names on this tree (1,020 on the trading
# box), which `fast_admission` counted as `off_hypothesis_lane` while naming a removal owner that
# had no limb to remove them. A screen that names a population its writer never removes is a
# queue with extra steps.
from research.merge_hypotheses import lane_router, split_by_lane, tradeable_universe  # noqa: E402


def _refuse_equities(symbol: str) -> str:
    """A stand-in router: the shape `lane_router` returns, without the registry."""
    return "event" if symbol in ("Apple", "GoldmanSachs") else ""


def test_the_merge_routes_equities_out_of_the_judging_docket() -> None:
    rows = [{"symbol": "XAUUSD", "family": "f"}, {"symbol": "Apple", "family": "f"},
            {"sym": "GoldmanSachs", "family": "f"}, {"symbol": "EURUSD", "family": "f"}]
    judged, off, by_lane, by_symbol = split_by_lane(rows, _refuse_equities, "now")
    assert [r.get("symbol") or r.get("sym") for r in judged] == ["XAUUSD", "EURUSD"]
    assert by_lane == {"event": 2}
    assert by_symbol == {"Apple": 1, "GoldmanSachs": 1}
    assert len(off) == 2


def test_a_routed_row_is_KEPT_and_carries_its_verdict_and_reason() -> None:
    """Never deleted. The event lane picks its population up by name instead of re-deriving it."""
    judged, off, _, _ = split_by_lane([{"symbol": "Apple", "family": "f"}],
                                      _refuse_equities, "2026-09-24T00:00:00")
    assert judged == []
    row = off[0]
    assert row["symbol"] == "Apple" and row["family"] == "f"     # the row itself survives intact
    assert row["lane"] == "event" and row["judging_status"] == "EVENT_LANE"
    assert row["routed_to_event_lane_at"] == "2026-09-24T00:00:00"
    why = row["judging_reason"]
    assert "2026-09-06" in why and "never hunted" in why
    # and it says what did NOT happen, so a later reader cannot mistake this for a reduction
    assert "stays tradable" in why and "bars and ticks are still collected" in why


def test_an_unprovable_router_routes_NOTHING() -> None:
    """Losing the registry must never empty the judge's docket (L1.28a).

    `lane()` answers UNCLASSIFIED for every symbol when it cannot read MetaTrader's registry, so a
    door that trusted it blindly would route the WHOLE docket away from the judge the first hour
    the file was unreadable. This is the same fail-open `tradeable_universe` already takes.
    """
    refusal, why = lane_router({})
    assert refusal is None
    assert "UNMEASURED" in why and "NOTHING" in why
    rows = [{"symbol": "Apple", "family": "f"}, {"symbol": "XAUUSD", "family": "f"}]
    judged, off, by_lane, _ = split_by_lane(rows, refusal, "now")
    assert len(judged) == 2 and off == [] and by_lane == {}


def test_a_row_that_names_no_instrument_is_not_routed_out() -> None:
    """The same rule the donation door keeps: a missing field is not a policy breach."""
    judged, off, _, _ = split_by_lane([{"family": "macro_conditional"}], _refuse_equities, "now")
    assert len(judged) == 1 and off == []


def test_the_router_is_proved_against_the_registry_before_it_routes_anything() -> None:
    """Against the real universe: FX and gold reach the judge, a share CFD does not."""
    universe = tradeable_universe()
    if not universe:
        import pytest
        pytest.skip("UNMEASURED: no universe registry on this host")
    refusal, why = lane_router(universe)
    assert refusal is not None and "proved on" in why
    assert refusal("XAUUSD") == "" and refusal("EURUSD") == ""
    equities = [s for s in universe.values() if refusal(s)]
    assert equities, "the registry carries share CFDs and none was routed out"


def test_unclassified_is_routed_out_because_absence_is_not_a_permission() -> None:
    """A real instrument whose class the desk has never seen is hunted by nothing."""
    judged, off, by_lane, _ = split_by_lane(
        [{"symbol": "NOTREAL", "family": "f"}],
        lambda s: "unclassified" if s == "NOTREAL" else "", "now")
    assert judged == [] and by_lane == {"unclassified": 1}
    assert off[0]["lane"] == "unclassified"


def test_the_door_is_wired_into_the_merge_and_publishes_its_verdict() -> None:
    """UNWIRED IS A DEFECT (III.16): a door nothing calls is a claim the desk cannot cash."""
    src = (DESK / "research" / "merge_hypotheses.py").read_text(encoding="utf-8")
    assert "lane_refusal, lane_why = lane_router(tradeable)" in src
    assert "split_by_lane(" in src
    # the merge report must carry the verdict AND whether the router could be proved, so
    # "nothing was routed this hour" never reads the same as "the registry was unreadable"
    assert '"event_lane": {' in src and '"proved": lane_refusal is not None' in src
