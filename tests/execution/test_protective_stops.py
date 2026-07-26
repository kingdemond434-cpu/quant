"""§3 host-death survivorship. These tests exist because a stop that ALMOST protects the book
reads identically to one that does, on every check short of comparing quantities."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from libs.execution.protective_stops import (
    NAKED_GRACE_S,
    NakedWatch,
    closing_side,
    is_protective_stop,
    naked_positions,
    reconcile,
    ruin_stop_price,
    stop_is_adequate,
)


def _stop(sym: str, side: str, qty: float, **kw):
    return {"symbol": sym, "side": side, "type": "STOP_MARKET",
            "reduceOnly": True, "origQty": qty, **kw}


class TestStopAdequacy:
    def test_a_full_cover_stop_is_adequate(self) -> None:
        assert stop_is_adequate(_stop("BTCUSDT", "SELL", 1.0), 1.0)

    def test_a_partial_stop_is_not_adequate(self) -> None:
        # the failure every presence-check misses: 80% of the position naked through the outage
        assert not stop_is_adequate(_stop("BTCUSDT", "SELL", 0.2), 1.0)

    def test_a_stop_on_the_wrong_side_is_not_a_stop(self) -> None:
        # BUY on a long position would DOUBLE it if it triggered
        assert not stop_is_adequate(_stop("BTCUSDT", "BUY", 1.0), 1.0)

    def test_a_limit_stop_is_not_accepted(self) -> None:
        o = _stop("BTCUSDT", "SELL", 1.0)
        o["type"] = "STOP_LIMIT"
        assert not stop_is_adequate(o, 1.0)

    def test_a_non_reduce_only_stop_is_not_accepted(self) -> None:
        o = _stop("BTCUSDT", "SELL", 1.0)
        o["reduceOnly"] = False
        assert not stop_is_adequate(o, 1.0)

    def test_string_true_from_the_venue_is_honoured(self) -> None:
        # Binance echoes booleans as JSON strings on some endpoints
        o = _stop("BTCUSDT", "SELL", 1.0)
        o["reduceOnly"] = "true"
        assert stop_is_adequate(o, 1.0)

    def test_shorts_close_by_buy(self) -> None:
        assert closing_side(-1.0) == "BUY"
        assert is_protective_stop(_stop("BTCUSDT", "BUY", 1.0), -1.0)

    def test_an_unreadable_quantity_contributes_no_cover(self) -> None:
        assert not stop_is_adequate(_stop("BTCUSDT", "SELL", "not-a-number"), 1.0)


class TestNakedDetection:
    def test_a_position_with_no_orders_at_all_is_naked(self) -> None:
        assert naked_positions({"BTCUSDT": 1.0}, []) == {"BTCUSDT": 1.0}

    def test_split_stops_summing_to_cover_are_not_naked(self) -> None:
        orders = [_stop("BTCUSDT", "SELL", 0.5), _stop("BTCUSDT", "SELL", 0.5)]
        assert naked_positions({"BTCUSDT": 1.0}, orders) == {}

    def test_another_symbols_stop_does_not_cover_this_one(self) -> None:
        orders = [_stop("ETHUSDT", "SELL", 100.0)]
        assert naked_positions({"BTCUSDT": 1.0}, orders) == {"BTCUSDT": 1.0}

    def test_zero_positions_are_ignored(self) -> None:
        assert naked_positions({"BTCUSDT": 0.0}, []) == {}

    def test_a_short_covered_by_a_buy_stop_is_clean(self) -> None:
        assert naked_positions({"BTCUSDT": -2.0}, [_stop("BTCUSDT", "BUY", 2.0)]) == {}

    @given(qty=st.floats(0.001, 1e6), cover=st.floats(0.0, 1e6))
    def test_coverage_is_monotone_in_stop_size(self, qty: float, cover: float) -> None:
        """More cover never turns a clean position naked. A property, not an example: this is
        the invariant a future 'optimisation' of the summing loop would silently break."""
        naked = naked_positions({"S": qty}, [_stop("S", "SELL", cover)])
        bigger = naked_positions({"S": qty}, [_stop("S", "SELL", cover * 2 + 1.0)])
        assert not (bigger and not naked)


class TestRuinStopPrice:
    def test_a_long_stop_sits_below_the_mark(self) -> None:
        p = ruin_stop_price(mark=100.0, position_qty=1.0, equity=1000.0)
        assert p is not None and 0 < p < 100.0

    def test_a_short_stop_sits_above_the_mark(self) -> None:
        p = ruin_stop_price(mark=100.0, position_qty=-1.0, equity=1000.0)
        assert p is not None and p > 100.0

    def test_the_stop_costs_exactly_the_ruin_budget(self) -> None:
        # budget 1000*0.05 = 50 over 2 units => 25/unit adverse => stop at 75
        p = ruin_stop_price(mark=100.0, position_qty=2.0, equity=1000.0, ruin_fraction=0.05)
        assert p is not None
        assert abs((100.0 - p) * 2.0 - 50.0) < 1e-6

    def test_a_position_already_sized_past_ruin_clamps_to_a_placeable_price(self) -> None:
        """Budget 350 against 200 of notional: price zero arrives before the budget is spent.
        The honest answer is the smallest placeable price, not a negative one the venue rejects
        (which would leave the position with NO stop -- fail-open on the one rail that matters)."""
        p = ruin_stop_price(mark=100.0, position_qty=2.0, equity=1000.0, ruin_fraction=0.35)
        assert p is not None and 0.0 < p < 1.0

    def test_bad_inputs_return_none_not_a_number(self) -> None:
        # None must be read as "cannot compute -> do not open", never as "no stop needed"
        assert ruin_stop_price(0.0, 1.0, 1000.0) is None
        assert ruin_stop_price(100.0, 0.0, 1000.0) is None
        assert ruin_stop_price(100.0, 1.0, 0.0) is None

    @given(mark=st.floats(0.01, 1e6), qty=st.floats(0.001, 1e4),
           equity=st.floats(1.0, 1e9))
    def test_a_long_stop_is_always_a_placeable_positive_price(
        self, mark: float, qty: float, equity: float
    ) -> None:
        p = ruin_stop_price(mark, qty, equity)
        assert p is not None and p > 0.0


class TestGraceClockSurvivesRestart:
    def test_the_clock_persists_across_a_fresh_load(self, tmp_path) -> None:
        """A process that dies and respawns inside the grace window must not reset the clock --
        the crash-loop is exactly the scenario the rail exists for."""
        p = tmp_path / "watch.json"
        w = NakedWatch.load(p)
        w.observe({"BTCUSDT": 1.0}, now=1000.0)
        w.save()
        reborn = NakedWatch.load(p)          # simulates the restart
        reborn.observe({"BTCUSDT": 1.0}, now=1000.0 + NAKED_GRACE_S + 1)
        assert "BTCUSDT" in reborn.breaches(1000.0 + NAKED_GRACE_S + 1)

    def test_within_grace_is_not_a_breach(self, tmp_path) -> None:
        w = NakedWatch.load(tmp_path / "w.json")
        w.observe({"BTCUSDT": 1.0}, now=1000.0)
        assert w.breaches(1000.0 + NAKED_GRACE_S - 1) == {}

    def test_a_covered_symbol_restarts_the_clock(self, tmp_path) -> None:
        w = NakedWatch.load(tmp_path / "w.json")
        w.observe({"BTCUSDT": 1.0}, now=1000.0)
        w.observe({}, now=1010.0)                      # stop placed
        w.observe({"BTCUSDT": 1.0}, now=1020.0)        # naked again, fresh clock
        assert w.breaches(1020.0 + NAKED_GRACE_S - 1) == {}


class TestReconcile:
    def test_a_breach_freezes_entries(self, tmp_path) -> None:
        w = NakedWatch.load(tmp_path / "w.json")
        reconcile({"BTCUSDT": 1.0}, [], 1000.0, w)
        rep = reconcile({"BTCUSDT": 1.0}, [], 1000.0 + NAKED_GRACE_S + 1, w)
        assert rep.freeze_entries and "BTCUSDT" in rep.breaches

    def test_a_clean_book_does_not_freeze(self, tmp_path) -> None:
        w = NakedWatch.load(tmp_path / "w.json")
        rep = reconcile({"BTCUSDT": 1.0}, [_stop("BTCUSDT", "SELL", 1.0)], 1000.0, w)
        assert not rep.freeze_entries and rep.naked == {}
