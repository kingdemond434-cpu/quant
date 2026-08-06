"""HOST-DEATH SURVIVORSHIP -- 87 statements on the risk path, and no test had ever reached them.

The rail that matters when the host dies is the one the VENUE holds. A stop enforced by our own
process is not a stop; it is an intention that evaporates with the process. So every assertion here
is stated against what Binance can see, and the file's own §7 bar -- risk-path code must be
property-testable -- was being met by construction and by nothing else.

THE THREE FAILURES THIS FILE EXISTS FOR, each of which passes a naive check:

  PARTIAL COVER      a 1.0-BTC position with a 0.2-BTC stop passes every "is there a stop?" check
                     ever written and leaves 80% of the book naked through the outage.
  WRONG KIND         a LIMIT stop can go unfilled through the very gap it exists for; a stop that
                     is not reduce-only OPENS a position on the far side; a stop on the wrong side
                     doubles the position instead of closing it.
  THE RESET LOOP     a process that dies and respawns every 45s resets the 60s clock forever and
                     never breaches -- which is exactly the crash-loop the rail is for. The timer
                     therefore has to survive process death, and that is asserted on disk.

And the false-alarm direction is asserted too, because it is what gets a rail switched off: two
0.5-BTC stops DO protect a 1.0-BTC position, and calling that naked would be the last thing this
rail ever did.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.execution import protective_stops as PS


def _stop(symbol: str = "BTCUSDT", side: str = "SELL", qty: float = 1.0,
          typ: str = "STOP_MARKET", reduce_only: object = True) -> dict:
    return {"symbol": symbol, "side": side, "type": typ, "origQty": qty,
            "reduceOnly": reduce_only}


# ------------------------------------------------------------------ side and price

def test_a_long_closes_by_SELL_and_a_short_by_BUY() -> None:
    """A stop on the wrong side does not close the position, it DOUBLES it."""
    assert PS.closing_side(1.0) == "SELL"
    assert PS.closing_side(-1.0) == "BUY"


def test_the_stop_sits_at_the_ruin_line_the_dead_man_uses() -> None:
    """Mirrors the dead-man's 35% ruin rail so the per-position stop sits AT the ruin line rather
    than somewhere unrelated to it. Two rails on different numbers is one rail and one surprise."""
    assert PS.RUIN_FRACTION == 0.35
    px = PS.ruin_stop_price(mark=100.0, position_qty=10.0, equity=1_000.0)
    assert px == pytest.approx(100.0 - (1_000.0 * 0.35) / 10.0)


def test_a_short_stop_is_ABOVE_the_mark_and_a_long_stop_below() -> None:
    long_px = PS.ruin_stop_price(100.0, 5.0, 1_000.0)
    short_px = PS.ruin_stop_price(100.0, -5.0, 1_000.0)
    assert long_px is not None and short_px is not None
    assert long_px < 100.0 < short_px


def test_a_bigger_position_gets_a_TIGHTER_stop_for_the_same_ruin_budget() -> None:
    """The budget is a fraction of EQUITY, not of notional: doubling the size halves the adverse
    move that spends it. A stop that ignored size would let a large position lose multiples of the
    ruin budget before firing."""
    small = PS.ruin_stop_price(100.0, 1.0, 1_000.0)
    large = PS.ruin_stop_price(100.0, 10.0, 1_000.0)
    assert small is not None and large is not None
    assert large > small, "the larger position must stop out closer to the mark"


def test_a_long_stop_is_clamped_POSITIVE_when_the_budget_exceeds_the_notional() -> None:
    """Price zero is reached before the budget is spent, and a stop at or below 0 is not
    placeable. The position is already sized past ruin, and the honest answer is the smallest
    positive price -- not a negative number the venue would reject and leave the position naked."""
    px = PS.ruin_stop_price(mark=10.0, position_qty=1.0, equity=1_000_000.0)
    assert px is not None and px > 0.0


@pytest.mark.parametrize(("mark", "qty", "equity"), [
    (0.0, 1.0, 1_000.0), (-1.0, 1.0, 1_000.0),
    (100.0, 0.0, 1_000.0),
    (100.0, 1.0, 0.0), (100.0, 1.0, -5.0),
])
def test_uncomputable_inputs_return_None_which_callers_read_as_DO_NOT_OPEN(mark, qty,
                                                                          equity) -> None:
    """None means 'cannot compute' and must never be read as 'no stop needed'. Fail-closed is the
    whole point of this file."""
    assert PS.ruin_stop_price(mark, qty, equity) is None


def test_a_non_positive_ruin_fraction_is_refused() -> None:
    assert PS.ruin_stop_price(100.0, 1.0, 1_000.0, ruin_fraction=0.0) is None


# ------------------------------------------------------------------ order kind

def test_a_LIMIT_stop_is_not_protective() -> None:
    """It can go unfilled through the very gap it exists for."""
    assert PS.is_protective_stop(_stop(typ="STOP_LIMIT"), 1.0) is False
    assert PS.is_protective_stop(_stop(typ="LIMIT"), 1.0) is False


def test_both_accepted_stop_type_spellings_work() -> None:
    for typ in ("STOP_MARKET", "STOP", "stop_market"):
        assert PS.is_protective_stop(_stop(typ=typ), 1.0) is True


def test_a_stop_that_is_not_reduce_only_is_not_protective() -> None:
    """It opens a new position on the far side instead of closing the one it was meant to cover."""
    assert PS.is_protective_stop(_stop(reduce_only=False), 1.0) is False
    assert PS.is_protective_stop({"symbol": "BTCUSDT", "side": "SELL",
                                  "type": "STOP_MARKET", "origQty": 1.0}, 1.0) is False


def test_the_venues_string_spelling_of_reduce_only_is_accepted() -> None:
    """Binance returns it as a JSON bool; some paths stringify it. Rejecting the string form would
    call every properly-stopped position naked and freeze the desk."""
    assert PS.is_protective_stop(_stop(reduce_only="true"), 1.0) is True
    assert PS.is_protective_stop(_stop(reduce_only="True"), 1.0) is True
    assert PS.is_protective_stop(_stop(reduce_only="false"), 1.0) is False


def test_the_snake_case_field_name_is_also_accepted() -> None:
    o = {"symbol": "BTCUSDT", "side": "SELL", "type": "STOP_MARKET", "origQty": 1.0,
         "reduce_only": True}
    assert PS.is_protective_stop(o, 1.0) is True


def test_a_stop_on_the_WRONG_SIDE_is_not_protective() -> None:
    assert PS.is_protective_stop(_stop(side="BUY"), 1.0) is False
    assert PS.is_protective_stop(_stop(side="SELL"), -1.0) is False


# ------------------------------------------------------------------ quantity

def test_an_unreadable_quantity_contributes_NO_cover() -> None:
    """Zero is the fail-closed reading: an order whose size cannot be parsed protects nothing that
    can be relied on."""
    assert PS.stop_qty({"origQty": "not-a-number"}) == 0.0
    assert PS.stop_qty({}) == 0.0
    assert PS.stop_qty({"origQty": None}) == 0.0


def test_both_quantity_field_spellings_are_read() -> None:
    assert PS.stop_qty({"origQty": 2.5}) == 2.5
    assert PS.stop_qty({"quantity": "3.5"}) == 3.5


def test_a_negative_quantity_is_read_as_size_not_as_negative_cover() -> None:
    assert PS.stop_qty({"origQty": -2.0}) == 2.0


def test_PARTIAL_COVER_is_naked_however_valid_the_order_looks() -> None:
    """THE SUBTLE FAILURE. A 1.0-BTC position with a 0.2-BTC stop passes every presence check ever
    written and leaves 80% of the book naked through the outage."""
    assert PS.stop_is_adequate(_stop(qty=0.2), 1.0) is False
    assert PS.naked_positions({"BTCUSDT": 1.0}, [_stop(qty=0.2)]) == {"BTCUSDT": 1.0}


def test_SPLIT_STOPS_are_summed_so_the_rail_does_not_cry_wolf() -> None:
    """Two 0.5-BTC stops DO protect a 1.0-BTC position. Testing per-order would call that naked,
    and a rail that false-alarms is a rail that gets switched off."""
    assert PS.naked_positions({"BTCUSDT": 1.0}, [_stop(qty=0.5), _stop(qty=0.5)]) == {}


def test_a_hair_under_full_cover_is_tolerated_but_a_real_shortfall_is_not() -> None:
    """Lot-size rounding leaves a few basis points uncovered on almost every real position."""
    assert PS.naked_positions({"BTCUSDT": 1.0}, [_stop(qty=0.999)]) == {}
    assert PS.naked_positions({"BTCUSDT": 1.0}, [_stop(qty=0.90)]) == {"BTCUSDT": 1.0}


def test_stops_on_OTHER_symbols_do_not_count_as_cover() -> None:
    """A cross-symbol match would report the whole book protected by one large stop on one ticker.
    """
    assert PS.naked_positions({"BTCUSDT": 1.0},
                              [_stop(symbol="ETHUSDT", qty=99.0)]) == {"BTCUSDT": 1.0}


def test_a_flat_symbol_is_not_naked() -> None:
    assert PS.naked_positions({"BTCUSDT": 0.0}, []) == {}


def test_a_short_position_is_protected_by_a_BUY_stop() -> None:
    assert PS.naked_positions({"BTCUSDT": -1.0}, [_stop(side="BUY", qty=1.0)]) == {}
    assert PS.naked_positions({"BTCUSDT": -1.0},
                              [_stop(side="SELL", qty=1.0)]) == {"BTCUSDT": -1.0}


# ------------------------------------------------------------------ the grace clock

def test_the_clock_SURVIVES_PROCESS_DEATH(tmp_path: Path) -> None:
    """THE INVARIANT IS TRIVIALLY DEFEATABLE OTHERWISE. A process that dies and respawns every 45s
    resets an in-memory timer forever and never breaches -- which is precisely the crash-loop
    scenario this rail exists for."""
    p = tmp_path / "watch.json"
    w = PS.NakedWatch(path=p)
    w.observe({"BTCUSDT": 1.0}, now=1_000.0)
    w.save()

    reborn = PS.NakedWatch.load(p)                     # the process died and came back
    assert reborn.first_seen["BTCUSDT"] == 1_000.0
    assert reborn.breaches(now=1_000.0 + PS.NAKED_GRACE_S + 1) == {"BTCUSDT": pytest.approx(61.0)}


def test_a_covered_symbol_drops_out_so_the_clock_restarts_clean(tmp_path: Path) -> None:
    """A stale timer would breach on a position that was covered minutes ago."""
    w = PS.NakedWatch(path=tmp_path / "w.json")
    w.observe({"BTCUSDT": 1.0}, now=100.0)
    w.observe({}, now=200.0)
    assert w.first_seen == {}
    assert w.breaches(now=100_000.0) == {}


def test_the_first_seen_time_is_not_refreshed_by_later_ticks(tmp_path: Path) -> None:
    """`setdefault`, not assignment. Refreshing it on every tick would reset the clock each poll
    and the grace period would never elapse."""
    w = PS.NakedWatch(path=tmp_path / "w.json")
    w.observe({"BTCUSDT": 1.0}, now=100.0)
    w.observe({"BTCUSDT": 1.0}, now=150.0)
    assert w.first_seen["BTCUSDT"] == 100.0


def test_within_grace_is_not_a_breach(tmp_path: Path) -> None:
    w = PS.NakedWatch(path=tmp_path / "w.json")
    w.observe({"BTCUSDT": 1.0}, now=0.0)
    assert w.breaches(now=PS.NAKED_GRACE_S) == {}, "the boundary is exclusive"
    assert w.breaches(now=PS.NAKED_GRACE_S + 0.01) != {}


def test_a_missing_or_corrupt_watch_file_loads_EMPTY_rather_than_crashing(tmp_path: Path) -> None:
    assert PS.NakedWatch.load(tmp_path / "absent.json").first_seen == {}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", "utf-8")
    assert PS.NakedWatch.load(bad).first_seen == {}
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"first_seen": {"BTCUSDT": "soon"}}), "utf-8")
    assert PS.NakedWatch.load(wrong).first_seen == {}


def test_the_watch_is_written_ATOMICALLY(tmp_path: Path) -> None:
    """A torn write on this file loses the clock, and losing the clock is the reset loop again --
    this time caused by the rail's own crash rather than the host's."""
    p = tmp_path / "w.json"
    w = PS.NakedWatch(first_seen={"BTCUSDT": 5.0}, path=p)
    w.save()
    assert json.loads(p.read_text("utf-8"))["first_seen"]["BTCUSDT"] == 5.0
    assert not p.with_suffix(".json.tmp").exists(), "the temp file must be renamed, not left"


# ------------------------------------------------------------------ the tick

def test_a_fully_stopped_book_freezes_nothing(tmp_path: Path) -> None:
    w = PS.NakedWatch(path=tmp_path / "w.json")
    rep = PS.reconcile({"BTCUSDT": 1.0}, [_stop(qty=1.0)], now=100.0, watch=w)
    assert rep.naked == {} and rep.freeze_entries is False
    assert "adequate venue-side stop" in rep.summary


def test_a_naked_position_within_grace_reports_but_does_not_freeze(tmp_path: Path) -> None:
    w = PS.NakedWatch(path=tmp_path / "w.json")
    rep = PS.reconcile({"BTCUSDT": 1.0}, [], now=100.0, watch=w)
    assert rep.naked == {"BTCUSDT": 1.0}
    assert rep.freeze_entries is False
    assert "within grace" in rep.summary


def test_a_breach_freezes_NEW_ENTRIES_and_does_not_flatten(tmp_path: Path) -> None:
    """Flattening into an unknown book state is its own risk, and the ladder owns that decision.
    A rail that liquidated on its own would be a second, unreviewed, risk policy."""
    w = PS.NakedWatch(path=tmp_path / "w.json")
    PS.reconcile({"BTCUSDT": 1.0}, [], now=0.0, watch=w)
    rep = PS.reconcile({"BTCUSDT": 1.0}, [], now=PS.NAKED_GRACE_S + 5, watch=w)
    assert rep.freeze_entries is True
    assert "grace" in rep.summary and str(int(PS.NAKED_GRACE_S)) in rep.summary


def test_reconcile_persists_the_watch_as_a_side_effect(tmp_path: Path) -> None:
    """The clock has to be on disk before the process can die, not after the next tick."""
    p = tmp_path / "w.json"
    PS.reconcile({"BTCUSDT": 1.0}, [], now=42.0, watch=PS.NakedWatch(path=p))
    assert json.loads(p.read_text("utf-8"))["first_seen"] == {"BTCUSDT": 42.0}


def test_the_report_counts_ALL_positions_not_only_the_naked_ones(tmp_path: Path) -> None:
    """'2 naked' means nothing without the denominator: 2 of 2 and 2 of 40 are different mornings.
    """
    w = PS.NakedWatch(path=tmp_path / "w.json")
    rep = PS.reconcile({"BTCUSDT": 1.0, "ETHUSDT": 2.0, "SOLUSDT": 3.0},
                       [_stop(symbol="SOLUSDT", qty=3.0)], now=1.0, watch=w)
    assert rep.n_positions == 3 and len(rep.naked) == 2
    assert "2 naked position(s) of 3" in rep.summary


def test_this_module_makes_no_exchange_calls() -> None:
    """The impure half lives in scripts/run_live_guard.py so this file stays property-testable,
    which is the §7 verification bar for risk-path code. A network import here would silently
    move that boundary."""
    src = Path(PS.__file__).read_text("utf-8")
    for banned in ("urllib", "requests", "httpx", "socket", "place_order", "hmac"):
        assert banned not in src, f"{banned} in a pure risk-logic module"
