"""The account breakers (`mt5desk.account_breaker`): a prop account's daily-loss circuit breaker
and the disconnect breaker, end to end against a scripted terminal.

What is pinned: the line is the VENUE's (never tighter by fiat), the buffer is MEASURED (open
risk's volatility or the stops, whichever is smaller, plus the spread to close) and shrinks to
zero with a flat book, a trip is confirmed by a second read and flattens for the venue day only,
it re-arms itself at the venue's boundary (17:00 New York for E8, midnight Prague for FTMO), a
disconnect or a lost heartbeat holds new orders until the venue reconciles OK and never closes
anything, and both breakers hold the order door shut on NEW risk only.
"""
from __future__ import annotations

import ast
import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import account_breaker as brk  # noqa: E402
from mt5desk import account_profile as acct  # noqa: E402
from mt5desk import order_door as door  # noqa: E402

# A summer weekday, 14:00 New York (18:00 UTC): venue day 2026-07-15 runs from 21:00Z on the 14th.
T0 = datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
E8 = brk.RULES["e8-pro-v2"]
FTMO2 = brk.RULES["ftmo-2step"]


class Term:
    """A scripted terminal. XAUUSD: tick size 0.01 worth 1.0 per lot, so 100 per 1.0 of price."""

    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_REMOVE = 8
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    def __init__(self, equity: float = 100_000.0, balance: float = 100_000.0, *,
                 connected: bool | None = True, positions: list[Any] | None = None,
                 orders: list[Any] | None = None, deals: list[Any] | None = None) -> None:
        self.equity, self.balance, self.connected = equity, balance, connected
        self.positions = list(positions or [])
        self.orders = list(orders or [])
        self.deals = deals
        self.bid, self.ask = 2000.0, 2000.5
        self.sent: list[dict[str, Any]] = []

    def terminal_info(self) -> Any:
        return None if self.connected is None else SimpleNamespace(connected=self.connected)

    def account_info(self) -> Any:
        return SimpleNamespace(equity=self.equity, balance=self.balance, login=7, server="S")

    def positions_get(self, **_: Any) -> tuple[Any, ...]:
        return tuple(self.positions)

    def orders_get(self, **_: Any) -> tuple[Any, ...]:
        return tuple(self.orders)

    def symbol_info(self, symbol: str) -> Any:
        return SimpleNamespace(trade_tick_value=1.0, trade_tick_size=0.01)

    def symbol_info_tick(self, symbol: str) -> Any:
        return SimpleNamespace(bid=self.bid, ask=self.ask, time=0)

    def history_deals_get(self, *_: Any) -> Any:
        return None if self.deals is None else tuple(self.deals)

    def order_check(self, req: dict[str, Any]) -> Any:
        return SimpleNamespace(retcode=0, comment="ok")

    def order_send(self, req: dict[str, Any]) -> Any:
        self.sent.append(dict(req))
        return SimpleNamespace(retcode=10009, comment="done", order=1, deal=1,
                               volume=req.get("volume", 0.0), price=req.get("price", 1.0))

    def last_error(self) -> Any:
        return (0, "")


def pos(volume: float = 1.0, price: float = 2000.0, sl: float = 1994.0, buy: bool = True,
        symbol: str = "XAUUSD") -> SimpleNamespace:
    return SimpleNamespace(symbol=symbol, volume=volume, price_current=price, sl=sl,
                           type=0 if buy else 1, ticket=11, magic=341953, comment="DWx")


def reading(term: Term, at: datetime = T0) -> brk.Reading:
    return brk.read_account(term, at)


def run(state: dict[str, Any], term: Term, rule: brk.VenueRule | None = E8, *,
        at: datetime = T0, initial: float | None = None, confirm: Term | None = None,
        derived: float | None = None) -> brk.Verdict:
    second = confirm or term
    return brk.evaluate(state, reading(term, at), rule, initial, "test rule",
                        derived_start_balance=derived,
                        confirm=lambda: reading(second, at))


def warm(state: dict[str, Any], term: Term, at: datetime = T0 - timedelta(seconds=60)) -> None:
    """One earlier reading on the same venue day (its deal history read: no deals today), then a
    reconcile: the ordinary steady state."""
    run(state, term, at=at, derived=term.balance)
    brk.note_reconcile(state, "OK")


# ------------------------------------------------------------------ the venue's rules
def test_rules_are_the_venues_own_numbers_never_restated() -> None:
    assert E8.daily_loss_frac == acct.E8_PRO.daily_loss_limit == 0.025
    assert brk.RULES["e8-one-8pct"].daily_loss_frac == acct.E8_ONE_8.daily_loss_limit
    assert "fusion-live" not in brk.RULES, "the main book has no daily-loss rule"
    from prop import ftmo_follower as fw
    assert {k.replace("ftmo-", "").replace("step", "-step"): v
            for k, v in brk.FTMO_DAILY.items()} == fw.ACCOUNT_TYPES
    assert brk.FTMO_MAX_LOSS == fw.MAX_LOSS_FRAC
    assert FTMO2.base == "initial" and FTMO2.day_tz == "Europe/Prague"


def test_the_cadence_constant_is_the_resident_loops() -> None:
    src = (_DESK / "research" / "gateway_resident.py").read_text(encoding="utf-8")
    assert f"INTERVAL_S = {int(brk.CADENCE_S)}" in src


def _declare(root: Path, accounts: dict[str, str], initial: dict[str, float] | None = None
             ) -> None:
    p = root / Path(*acct.DECLARATIONS_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {"accounts": accounts}
    if initial is not None:
        doc["initial_balances"] = initial
    p.write_text(json.dumps(doc), encoding="utf-8")


def test_rule_for_connected_main_book_untouched_and_unknowns_fail_closed(tmp_path: Path) -> None:
    acc = {"login": 7, "server": "S"}
    assert brk.rule_for_connected(acc, tmp_path)[0] is None          # no declarations at all
    _declare(tmp_path, {"7@S": "fusion-live"})
    assert brk.rule_for_connected(acc, tmp_path)[0] is None          # declared, no daily rule
    _declare(tmp_path, {"7@S": "e8-one-8pct"})
    assert brk.rule_for_connected(acc, tmp_path)[0] == brk.RULES["e8-one-8pct"]
    _declare(tmp_path, {"8@S": "e8-one-8pct"})
    assert brk.rule_for_connected(acc, tmp_path)[0] == E8             # undeclared: tightest
    _declare(tmp_path, {"7@S": "made-up"})
    assert brk.rule_for_connected(acc, tmp_path)[0] == E8
    _declare(tmp_path, {"7@S": "ftmo-2step"}, {"7@S": 100_000})
    rule, initial, why = brk.rule_for_connected(acc, tmp_path)
    assert rule == FTMO2 and initial == 100_000.0 and "7@S" not in why


# ------------------------------------------------------------------ the venue day
@pytest.mark.parametrize("utc,day", [
    (datetime(2026, 7, 15, 20, 59, tzinfo=UTC), "2026-07-15"),   # 16:59 New York (EDT)
    (datetime(2026, 7, 15, 21, 0, tzinfo=UTC), "2026-07-16"),    # 17:00 New York: broker midnight
    (datetime(2026, 1, 15, 21, 59, tzinfo=UTC), "2026-01-15"),   # 16:59 New York (EST)
    (datetime(2026, 1, 15, 22, 0, tzinfo=UTC), "2026-01-16"),
])
def test_venue_day_rolls_at_broker_midnight_both_seasons(utc: datetime, day: str) -> None:
    assert brk.venue_day(utc) == day
    start = brk.venue_day_start(day)
    assert brk.venue_day(start) == day and brk.venue_day(start - timedelta(seconds=1)) != day


def test_ftmo_day_rolls_at_prague_midnight() -> None:
    assert brk.venue_day(datetime(2026, 7, 15, 21, 59, tzinfo=UTC), "Europe/Prague", 0) \
        == "2026-07-15"
    assert brk.venue_day(datetime(2026, 7, 15, 22, 0, tzinfo=UTC), "Europe/Prague", 0) \
        == "2026-07-16"


def test_broker_epoch_is_new_york_plus_seven() -> None:
    at = datetime(2026, 7, 15, 21, 0, tzinfo=UTC)     # 17:00 EDT -> broker 00:00 next day
    assert brk.broker_epoch(at) == datetime(2026, 7, 16, 0, 0, tzinfo=UTC).timestamp()


# ------------------------------------------------------------------ reading the open risk
def test_reading_prices_notional_stops_and_the_close() -> None:
    r = reading(Term(positions=[pos(volume=1.0, price=2000.0, sl=1994.0)]))
    assert r.ok and r.notional == pytest.approx(200_000.0)
    assert r.stop_bound == pytest.approx(600.0)
    assert r.close_cost == pytest.approx(50.0) and r.symbols == ["XAUUSD"]


def test_a_leg_without_a_stop_has_no_stop_bound() -> None:
    assert reading(Term(positions=[pos(sl=0.0)])).stop_bound == math.inf


def test_a_bracket_counts_its_larger_side_once() -> None:
    buy = SimpleNamespace(symbol="XAUUSD", type=4, volume_current=1.0, price_open=2010.0,
                          sl=2004.0)
    sell = SimpleNamespace(symbol="XAUUSD", type=5, volume_current=0.5, price_open=1990.0,
                           sl=1996.0)
    r = reading(Term(orders=[buy, sell]))
    assert r.notional == pytest.approx(201_000.0) and r.stop_bound == pytest.approx(600.0)


@pytest.mark.parametrize("connected", [False, None])
def test_no_broker_connection_is_not_a_reading(connected: bool | None) -> None:
    r = reading(Term(connected=connected))
    assert not r.ok and r.why


# ------------------------------------------------------------------ the measured buffer
def test_a_flat_book_trips_exactly_at_the_venues_line() -> None:
    assert brk.buffer_for(0.0, 0.0, 0.0, None, 60.0)[0] == 0.0


def test_the_buffer_is_the_smaller_measured_bound_plus_the_close() -> None:
    by_vol, _ = brk.buffer_for(200_000.0, 600.0, 50.0, 1e-5, 100.0)     # 200k x 1e-5 x 10 = 20
    assert by_vol == pytest.approx(70.0)
    by_stop, _ = brk.buffer_for(200_000.0, 600.0, 50.0, 1e-3, 100.0)    # vol says 2000
    assert by_stop == pytest.approx(650.0)
    assert brk.buffer_for(200_000.0, math.inf, 50.0, None, 100.0)[0] is None   # nothing measured


def test_the_buffer_is_two_sided_less_open_risk_less_buffer() -> None:
    big, _ = brk.buffer_for(200_000.0, 600.0, 50.0, None, 60.0)
    small, _ = brk.buffer_for(20_000.0, 60.0, 5.0, None, 60.0)
    assert small < big


def test_gap_threshold_falls_back_to_one_missed_pass_then_measures() -> None:
    assert brk.gap_threshold([60.0] * 10)[0] == brk.FALLBACK_GAP_S
    gaps = [58.0, 60.0, 61.0, 63.0] * (brk.MIN_READINGS // 4)
    thr, basis = brk.gap_threshold(gaps)
    assert 63.0 < thr < 90.0 and basis.startswith("measured")


def test_volatility_is_measured_from_the_books_own_moves() -> None:
    state: dict[str, Any] = {}
    term = Term(positions=[pos(sl=0.0)])
    for i in range(brk.MIN_READINGS + 2):
        term.equity = 100_000.0 + (20.0 if i % 2 else 0.0)
        run(state, term, at=T0 - timedelta(seconds=60 * (brk.MIN_READINGS + 2 - i)))
    zm, n = brk.z_max(state["z_days"])
    assert n >= brk.MIN_READINGS
    assert zm == pytest.approx(20.0 / 200_000.0 / math.sqrt(60.0))
    term.equity = 100_000.0
    v = run(state, term)
    assert v.zmax == pytest.approx(zm) and v.buffer is not None and v.buffer < 600.0
    assert v.buffer_why.startswith("volatility")


# ------------------------------------------------------------------ the daily-loss breaker
def test_trips_before_the_venues_line_and_flattens_for_the_venue_day() -> None:
    state: dict[str, Any] = {}
    term = Term(positions=[pos()])
    warm(state, term)
    term.equity = 98_100.0          # 2,500 floor at 97,500; buffer 600 to the stop + 50 to close
    v = run(state, term)
    assert v.floor == pytest.approx(97_500.0) and v.buffer == pytest.approx(650.0)
    assert v.tripped and v.newly_tripped and v.flatten_symbols == ["XAUUSD"]
    assert not v.new_risk_ok and v.equity > v.floor, "it trips BEFORE the venue's line"
    later = run(state, term, at=T0 + timedelta(hours=1))
    assert later.tripped and not later.newly_tripped and later.flatten_symbols == ["XAUUSD"]
    nxt = run(state, Term(equity=98_100.0, balance=98_100.0), at=T0 + timedelta(hours=4))
    assert nxt.day == "2026-07-16" and not nxt.tripped, "it re-arms at the venue's boundary"


def test_floating_loss_counts_balance_alone_does_not_hide_it() -> None:
    state: dict[str, Any] = {}
    term = Term(positions=[pos()])
    warm(state, term)
    term.equity = 98_000.0             # balance still 100k: the loss is all floating
    assert run(state, term).tripped


def test_above_the_line_nothing_happens() -> None:
    state: dict[str, Any] = {}
    term = Term(positions=[pos()])
    warm(state, term)
    term.equity = 98_200.0
    v = run(state, term)
    assert not v.tripped and v.new_risk_ok and not v.flatten_symbols


def test_one_torn_read_does_not_flatten() -> None:
    state: dict[str, Any] = {}
    term = Term(positions=[pos()])
    warm(state, term)
    term.equity = 98_000.0
    v = run(state, term, confirm=Term(equity=99_900.0, positions=[pos()]))
    assert not v.tripped and "confirming" in v.why and "tripped" not in state


def test_the_anchor_never_loosens_on_a_late_first_pass() -> None:
    state: dict[str, Any] = {}
    run(state, Term(equity=100_500.0, balance=100_000.0),
        at=brk.venue_day_start("2026-07-15") - timedelta(seconds=30))
    brk.note_reconcile(state, "OK")
    # The first reading of the new day comes after a loss; the anchor stays at the higher figure.
    v = run(state, Term(equity=99_000.0, balance=99_000.0),
            at=brk.venue_day_start("2026-07-15") + timedelta(seconds=30))
    assert state["anchor"]["value"] == pytest.approx(100_500.0)
    assert v.floor == pytest.approx(100_500.0 * (1 - 0.025))


def test_the_deal_history_restores_the_days_start_balance() -> None:
    state: dict[str, Any] = {}
    term = Term(equity=97_400.0, balance=97_400.0)
    v = run(state, term, derived=100_000.0)
    assert state["anchor"]["value"] == pytest.approx(100_000.0) and v.tripped


def test_day_start_balance_reads_deals_on_the_broker_clock() -> None:
    start = brk.venue_day_start("2026-07-15")
    since = brk.broker_epoch(start)
    deals = [SimpleNamespace(time=since - 10, profit=-999.0),      # yesterday's: ignored
             SimpleNamespace(time=since + 10, profit=-1_500.0, commission=-7.0, swap=0.0)]
    got = brk.day_start_balance(Term(deals=deals), 98_493.0, "2026-07-15", now=T0)
    assert got == pytest.approx(100_000.0)
    assert brk.day_start_balance(Term(deals=None), 1.0, "2026-07-15", now=T0) is None
    bad = [SimpleNamespace(time=None, profit=1.0)]
    assert brk.day_start_balance(Term(deals=bad), 1.0, "2026-07-15", now=T0) is None


def test_a_first_ever_reading_mid_day_without_history_holds_new_risk() -> None:
    v = run({}, Term())
    assert not v.account_ok and not v.new_risk_ok and not v.tripped and not v.flatten_symbols


def test_ftmo_needs_its_initial_balance_and_binds_its_max_loss() -> None:
    state: dict[str, Any] = {}
    term = Term(equity=95_000.0, balance=95_000.0)
    warm(state, term)
    v = run(state, term, rule=FTMO2)
    assert not v.account_ok and not v.new_risk_ok and not v.tripped
    v = run(state, term, rule=FTMO2, initial=100_000.0)
    # Daily: 95,000 - 5% of 100,000 = 90,000; the static 10% maximum loss floor is also 90,000.
    assert v.floor == pytest.approx(90_000.0) and v.new_risk_ok
    term.equity = term.balance = 91_000.0
    v = run(state, term, rule=FTMO2, initial=100_000.0, at=T0 + timedelta(days=1))
    assert v.floor == pytest.approx(90_000.0), "the 10% maximum loss binds over the daily line"


def test_the_main_book_has_no_daily_breaker() -> None:
    state: dict[str, Any] = {}
    term = Term(equity=50_000.0, positions=[pos()])
    warm(state, term)
    v = run(state, term, rule=None)
    assert not v.applicable and not v.tripped and v.new_risk_ok and v.floor is None


def test_an_order_that_would_enter_the_trip_zone_is_refused() -> None:
    state: dict[str, Any] = {}
    term = Term(equity=98_150.0)         # 650 above the 97,500 floor
    warm(state, term)
    v = run(state, term)
    assert v.new_risk_ok
    big = brk.order_legs(term, {"symbol": "XAUUSD", "type": 0, "volume": 1.0, "price": 2000.5,
                                "sl": 1994.0})
    assert brk.projected_refusal(v, reading(term), big)
    small = brk.order_legs(term, {"symbol": "XAUUSD", "type": 0, "volume": 0.1,
                                  "price": 2000.5, "sl": 1994.0})
    assert brk.projected_refusal(v, reading(term), small) is None


# ------------------------------------------------------------------ the disconnect breaker
def test_a_dead_connection_holds_new_orders_and_closes_nothing() -> None:
    state: dict[str, Any] = {}
    warm(state, Term(positions=[pos()]))
    v = run(state, Term(connected=False, positions=[pos()]))
    assert v.reconcile_required and not v.new_risk_ok and not v.flatten_symbols


def test_a_lost_heartbeat_waits_for_an_ok_reconcile() -> None:
    state: dict[str, Any] = {}
    term = Term()
    warm(state, term)
    v = run(state, term, at=T0 + timedelta(seconds=brk.FALLBACK_GAP_S + 60))
    assert v.reconcile_required and not v.new_risk_ok and "heartbeat lost" in v.why + str(
        state["disconnect"])
    assert not brk.note_reconcile(state, "UNMEASURED")
    assert state["disconnect"]["reconcile_required"]
    assert brk.note_reconcile(state, "OK")
    v = run(state, term, at=T0 + timedelta(seconds=brk.FALLBACK_GAP_S + 120))
    assert v.new_risk_ok


def test_an_ordinary_gap_needs_no_reconcile() -> None:
    state: dict[str, Any] = {}
    term = Term()
    warm(state, term, at=T0 - timedelta(seconds=60))
    assert run(state, term).new_risk_ok


def test_state_survives_a_restart(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    state: dict[str, Any] = {}
    term = Term(positions=[pos()])
    warm(state, term)
    term.equity = 98_000.0
    run(state, term)
    brk.save_state(state, p)
    again = brk.load_state(p)
    assert run(again, term, at=T0 + timedelta(minutes=1)).tripped


# ------------------------------------------------------------------ the door holds NEW risk only
@pytest.fixture
def _door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    door._MEMORY_IN_DOUBT.clear()
    yield
    door.OPEN_GATES.clear()
    door._MEMORY_IN_DOUBT.clear()


def test_a_gate_refuses_opens_and_never_a_close(_door: None) -> None:
    term = Term()
    asked: list[dict[str, Any]] = []

    def gate(_mt5: Any, req: Any) -> str | None:
        asked.append(dict(req))
        return "held"

    door.register_open_gate("account_breaker", gate)
    res = door.send(term, {"action": 1, "symbol": "XAUUSD", "volume": 0.1, "type": 0,
                           "price": 2000.5, "sl": 1990.0, "comment": "DWx"})
    assert res.door_refused and res.door_reason == "account_breaker" and not term.sent
    assert door.is_door_own_refusal(res)
    door.send(term, {"action": 1, "symbol": "XAUUSD", "volume": 0.1, "type": 1,
                     "position": 11, "price": 2000.0})
    door.send(term, {"action": 8, "order": 5})
    assert len(term.sent) == 2 and len(asked) == 1, "a close or a cancel is never asked"


def test_a_gate_that_raises_fails_closed(_door: None) -> None:
    term = Term()

    def gate(_mt5: Any, _req: Any) -> str | None:
        raise RuntimeError("boom")

    door.register_open_gate("account_breaker", gate)
    res = door.send(term, {"action": 1, "symbol": "XAUUSD", "volume": 0.1, "type": 0,
                           "price": 2000.5, "sl": 1990.0})
    assert res.door_refused and not term.sent
    door.clear_open_gate("account_breaker")
    door.send(term, {"action": 1, "symbol": "XAUUSD", "volume": 0.1, "type": 0,
                     "price": 2000.5, "sl": 1990.0})
    assert len(term.sent) == 1


# ------------------------------------------------------------------ the gateway's wiring
def _sdk(gw: Any, term: Term, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("terminal_info", "account_info", "positions_get", "orders_get", "symbol_info",
                 "symbol_info_tick", "history_deals_get", "order_check", "order_send",
                 "last_error"):
        monkeypatch.setattr(gw._test_sdk, name, getattr(term, name))


def test_gateway_pass_flattens_a_tripped_prop_account(portable_gateway: Any, tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    gw = portable_gateway
    monkeypatch.setattr(brk, "STATE", tmp_path / "breaker.json")
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    monkeypatch.setattr(brk, "rule_for_connected", lambda acc, root: (E8, None, "declared"))
    flat: list[tuple[str, str]] = []
    monkeypatch.setattr(gw, "cancel_pending", lambda st, s: flat.append(("cancel", s)))
    monkeypatch.setattr(gw, "close_positions", lambda st, s: flat.append(("close", s)))
    term = Term(positions=[pos()], deals=[])
    _sdk(gw, term, monkeypatch)
    v = gw.account_breaker_pass({"armed": True})
    assert v is not None and not v.tripped and "account_breaker" in door.OPEN_GATES
    gw.account_breaker_reconciled("OK")
    assert gw.account_breaker_new_risk()[0]
    term.equity = 98_000.0
    v = gw.account_breaker_pass({"armed": True})
    assert v.tripped and flat == [("cancel", "XAUUSD"), ("close", "XAUUSD")]
    assert not gw.account_breaker_new_risk()[0]
    refusal = gw.account_breaker_gate(gw._test_sdk, {"symbol": "XAUUSD", "volume": 0.1,
                                                     "type": 0, "price": 2000.5, "sl": 1990.0,
                                                     "comment": "DWx"})
    assert refusal and "daily-loss" in refusal
    saved = json.loads((tmp_path / "breaker.json").read_text(encoding="utf-8"))
    assert saved["tripped"]["day"] == v.day and saved["verdict"]["new_risk_ok"] is False
    door.OPEN_GATES.clear()


def test_gateway_pass_on_the_main_book_holds_only_until_reconciled(
        portable_gateway: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gw = portable_gateway
    monkeypatch.setattr(brk, "STATE", tmp_path / "breaker.json")
    monkeypatch.setattr(brk, "rule_for_connected", lambda acc, root: (None, None, "main"))
    term = Term(equity=10.0, positions=[pos()])
    _sdk(gw, term, monkeypatch)
    v = gw.account_breaker_pass({"armed": True})
    assert v is not None and not v.applicable and v.reconcile_required
    assert gw.account_breaker_gate(gw._test_sdk, {"symbol": "XAUUSD"})
    gw.account_breaker_reconciled("OK")
    assert gw.account_breaker_new_risk() == (True, "")
    term.connected = False
    assert "connection" in (gw.account_breaker_gate(gw._test_sdk, {"symbol": "XAUUSD"}) or "")
    door.OPEN_GATES.clear()


def test_gateway_pass_never_raises_and_then_holds_new_risk(
        portable_gateway: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    gw = portable_gateway

    def boom(*_: Any, **__: Any) -> Any:
        raise RuntimeError("broken")

    monkeypatch.setattr(brk, "read_account", boom)
    assert gw.account_breaker_pass({"armed": True}) is None
    assert gw.account_breaker_new_risk()[0] is False
    door.OPEN_GATES.clear()


def test_main_runs_the_breakers_before_anything_and_obeys_them() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    main = next(n for n in ast.parse(src).body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.get_source_segment(src, main) or ""
    first = body.index("account_breaker_pass(st)")
    assert first < body.index("restart_reconcile(") < body.index("account_breaker_reconciled(")
    assert body.index("account_breaker_reconciled(") < body.index("account_breaker_new_risk()")
    assert body.index("account_breaker_pass(st)") < body.index("manage_open_positions(")
    assert body.index("gateway_paused()") < first
    assert "account_breaker_reconciled(_rr_verdict)" in body, (
        "only THIS pass's reconcile verdict may lift the hold; a stale OK in `st` must not")


def test_every_trip_and_refusal_has_a_missed_growth_line() -> None:
    from mt5desk import fusion_rails
    import missed_growth as mg
    for rail in ("account_daily_breaker", "disconnect_breaker"):
        assert rail in fusion_rails.RAILS and rail in mg.FUSION_RAIL_NAMES


def test_the_new_money_file_is_in_the_reviewers_closure() -> None:
    rows = (_ROOT / "ops" / "money_closure.txt").read_text(encoding="utf-8").splitlines()
    assert "desks/mt5/mt5desk/account_breaker.py" in rows
