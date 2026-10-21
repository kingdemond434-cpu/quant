"""THE FTMO FOLLOWER (prop/ftmo_follower.py): one gold_asia order in E8's filled direction.

A stubbed MT5 terminal and fake IDs only. E8's published state is written the way E8-Gold and the
gold OCO write it: the pass report, the shared direction state and E8's gold lane state.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cross_account as xa  # noqa: E402
from mt5desk import gold_oco as oco  # noqa: E402
from prop import ftmo_follower as ff  # noqa: E402

FT_LOGIN, FT_SERVER = 63456789, "FTMO-Server2"          # fake
#: Fake: the conftest's DECLARED E8 identity (CONFTEST_LOGINS/SERVERS["e8"]); r7.1 declares
#: E8_ACCOUNT.json under it and the OCO's key join refuses any other E8 key (v2s).
E8_LOGIN, E8_SERVER = 31337, "E8-Test"
NOW = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)          # 07:30 CET, 01:30 New York
TICK = int((NOW + timedelta(hours=3)).timestamp())       # 08:30 on the UTC+3 server clock
DAY = "2026-10-21"
E8_POS = 777


class _MT5:
    TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_SLTP, TRADE_ACTION_REMOVE = 1, 5, 6, 8
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT = 0, 1, 2, 3
    ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 4, 5
    ORDER_TIME_GTC, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2

    def __init__(self, *, bid: float = 4329.8, ask: float = 4330.0, login: Any = FT_LOGIN,
                 server: str = FT_SERVER, trade_mode: int = 0, equity: float = 100_000.0,
                 balance: float = 100_000.0, deals: tuple = (), tick: int = TICK) -> None:
        self.bid, self.ask, self.tick = bid, ask, tick
        self.acc = SimpleNamespace(login=login, server=server, trade_mode=trade_mode,
                                   equity=equity, balance=balance)
        self.deals = deals
        #: Orders that left the book (removed or filled), as MT5's history_orders_get has them.
        self.hist_orders: list[SimpleNamespace] = []
        self.positions: list[SimpleNamespace] = []
        self.orders: list[SimpleNamespace] = []
        self.sent: list[dict] = []

    def account_info(self) -> SimpleNamespace:
        return self.acc

    def symbol_info_tick(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(time=self.tick, bid=self.bid, ask=self.ask)

    def symbol_info(self, symbol: str) -> SimpleNamespace:
        return SimpleNamespace(trade_contract_size=100.0, volume_min=0.01, volume_step=0.01,
                               volume_max=50.0)

    def positions_get(self, symbol: str | None = None) -> list:
        return list(self.positions)

    def orders_get(self, symbol: str | None = None) -> list:
        return list(self.orders)

    def history_deals_get(self, since: datetime, until: datetime) -> tuple | None:
        return self.deals

    def history_orders_get(self, since: datetime, until: datetime) -> list | None:
        return list(self.hist_orders)

    def order_send(self, req: dict) -> SimpleNamespace:
        self.sent.append(req)
        ticket = 9000 + len(self.sent)
        if req["action"] == self.TRADE_ACTION_PENDING:
            self.orders.append(SimpleNamespace(ticket=ticket, symbol="XAUUSD", type=req["type"],
                                               magic=req["magic"], price_open=req["price"],
                                               sl=req["sl"], volume_current=req["volume"],
                                               time_setup=self.tick))
        if req["action"] == self.TRADE_ACTION_REMOVE:
            self.hist_orders += [o for o in self.orders if o.ticket == req["order"]]
            self.orders = [o for o in self.orders if o.ticket != req["order"]]
        return SimpleNamespace(retcode=10009, order=ticket)


def _e8_report(*, at: datetime = NOW, status: str = "OK", guard: str | None = None,
               position_id: int | None = E8_POS, actions: list | None = None) -> dict:
    doc: dict[str, Any] = {"at": at.isoformat(), "status": status, "actions": actions or [],
                           "state": {"date": DAY, "carried": {}, "windows": {"asia": {
                               "placed_hour": 7.0, "position_id": position_id, "shadow": False,
                               "orders": {"buy_stop": {"id": 501, "price": 4340.0, "sl": 4320.0,
                                                       "tp": 4380.0, "lot": 1.0},
                                          "sell_stop": {"id": 502, "price": 4300.0,
                                                        "sl": 4320.0, "tp": 4260.0,
                                                        "lot": 1.0}}}}}}
    if guard:
        doc["guard"] = guard
    return doc


@pytest.fixture
def world(monkeypatch, tmp_path) -> SimpleNamespace:
    """E8 filled its asia buy stop today (position 777 open long), the direction state says so,
    FTMO is declared, its account file and the ftmo cert block are in place, and it is ARMED."""
    for name in ("STATE", "OUT", "INTENTS", "LOG", "PROP_LEDGER"):
        monkeypatch.setattr(ff, name, tmp_path / f"{name.lower()}.json")
    acct = tmp_path / "FTMO_LIVE_ACCOUNT.json"
    acct.write_text(json.dumps({"login": FT_LOGIN, "server": FT_SERVER, "trade_mode": 0,
                                "initial_balance": 100_000.0, "account_type": "2-step"}),
                    "utf-8")
    monkeypatch.setattr(ff, "ACCOUNT_FILE", acct)
    marker = tmp_path / "FTMO_FOLLOWER_ARMED"
    marker.write_text("", "utf-8")
    monkeypatch.setattr(ff, "ARMED_MARKER", marker)
    cert = tmp_path / "CERT_BOOK_LIVE.json"
    cert.write_text(json.dumps({"enabled": True, "ftmo": {"gold_asia": 0.009}}), "utf-8")
    monkeypatch.setattr(ff, "CERT_BOOK_FILE", cert)
    report = tmp_path / "E8_GOLD.json"
    report.write_text(json.dumps(_e8_report()), "utf-8")
    monkeypatch.setattr(ff, "E8_REPORT", report)
    oco.MODE_FILE.write_text(json.dumps({"lanes": ["e8", "fusion", "ftmo"],
                                         "modes": {"fusion": "fallback", "ftmo": "fallback"}}))
    e8k = oco.oco_account_key(E8_LOGIN, E8_SERVER)
    oco.publish_lane("e8", e8k, positions=[{"id": E8_POS, "side": "long", "opened_date": DAY}],
                     orders=[], date=DAY)
    oco.publish_lane("fusion", oco.oco_account_key(72345678, "FusionMarkets-Test"),
                     positions=[], orders=[], date=DAY)
    assert oco.claim_fill("e8", e8k, "buy", date=DAY)["won"]
    return SimpleNamespace(tmp=tmp_path, report=report, cert=cert, acct=acct, e8_key=e8k)


def _pass(mt5: _MT5, *, armed: bool = True, now: datetime = NOW) -> dict:
    return ff.run(mt5, armed=armed, now=now)


def _rows() -> list[dict]:
    p = Path(ff.INTENTS)
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()] \
        if p.exists() else []


def _entries(mt5: _MT5) -> list[dict]:
    return [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_PENDING]


# ======================================================================== the follow

def test_an_e8_long_fill_is_followed_by_exactly_one_long_order(world) -> None:
    mt5 = _MT5()
    doc = _pass(mt5)
    (req,) = _entries(mt5)
    assert req["type"] == mt5.ORDER_TYPE_BUY_STOP                # ask 4330 is short of 4340
    assert (req["price"], req["sl"], req["tp"]) == (4340.0, 4320.0, 4380.0)   # E8's own levels
    assert req["volume"] == pytest.approx(0.45)                  # 0.009 x 100k / (20 x 100)
    assert req["magic"] == ff.MAGIC and doc["status"] == "OK"
    _pass(mt5)
    _pass(mt5, now=NOW + timedelta(minutes=1))
    assert len(_entries(mt5)) == 1                               # one order a day
    sent = [r for r in _rows() if r.get("status") == "SENT"]
    assert len(sent) == 1 and sent[0]["side"] == "long"


def test_a_price_already_through_the_level_rests_a_limit_at_it_never_a_chase(world) -> None:
    mt5 = _MT5(bid=4344.8, ask=4345.0)
    _pass(mt5)
    (req,) = _entries(mt5)
    assert req["type"] == mt5.ORDER_TYPE_BUY_LIMIT and req["price"] == 4340.0


def test_before_e8_fills_nothing_is_placed(world) -> None:
    world.report.write_text(json.dumps(_e8_report(position_id=None)), "utf-8")
    mt5 = _MT5()
    doc = _pass(mt5)
    assert mt5.sent == [] and doc["follow"]["action"] == "wait"


# ======================================================================== never the other way

def test_an_ftmo_position_against_e8_refuses_and_alerts(world) -> None:
    mt5 = _MT5()
    mt5.positions = [SimpleNamespace(ticket=42, symbol="XAUUSD", type=1, magic=0, volume=0.1,
                                     sl=0.0, tp=0.0, time=TICK)]          # a MANUAL short
    doc = _pass(mt5)
    assert _entries(mt5) == [] and doc["alerts"]
    assert any(r.get("reason") == "opposite_exposure" for r in _rows())


def test_a_resting_ftmo_order_against_e8_refuses_too(world) -> None:
    mt5 = _MT5()
    mt5.orders = [SimpleNamespace(ticket=43, symbol="XAUUSD", type=5, magic=0,
                                  price_open=4300.0)]
    _pass(mt5)
    assert _entries(mt5) == []


# ======================================================================== E8 unreadable

@pytest.mark.parametrize("damage", ["absent", "stale", "torn", "not_ok", "direction_torn",
                                    "e8_lane_stale"])
def test_an_unreadable_e8_state_places_nothing_and_says_why(world, damage: str) -> None:
    if damage == "absent":
        world.report.unlink()
    elif damage == "stale":
        world.report.write_text(json.dumps(_e8_report(at=NOW - timedelta(minutes=11))), "utf-8")
    elif damage == "torn":
        world.report.write_text('{"at": "' + NOW.isoformat() + '", "status": "OK"', "utf-8")
    elif damage == "not_ok":
        world.report.write_text(json.dumps(_e8_report(status="MT5_UNAVAILABLE")), "utf-8")
    elif damage == "direction_torn":
        p = oco.direction_path()
        body = json.loads(p.read_text("utf-8"))
        body["tampered"] = True
        p.write_text(json.dumps(body), "utf-8")
    elif damage == "e8_lane_stale":
        oco.publish_lane("e8", world.e8_key, positions=[{"id": E8_POS, "side": "long"}],
                         orders=[], date=DAY,
                         now=datetime.now(tz=UTC) - timedelta(seconds=oco.MAX_STATE_AGE_S + 5))
    mt5 = _MT5()
    doc = _pass(mt5)
    want = "e8_stale" if damage in ("stale", "e8_lane_stale") else "unreadable"
    assert mt5.sent == [] and doc["follow"]["action"] == want
    (row,) = [r for r in _rows() if r.get("status") == "RAIL_BLOCKED"]
    assert row["rail"] == ff.RAIL and row["reason"] == want and row["why"]


# ======================================================================== v2r: E8 staleness

def test_the_e8_staleness_bound_is_one_pass_plus_its_grace_from_e8s_cadence(
        monkeypatch) -> None:
    """300 s (one E8 pass) + the 4-min run limit r7's E8_GOLD_SEND_GRACE_MIN (10 = 1 + 5 + 4)
    is derived from; an unreadable grace leaves one bare pass (tighter, never looser)."""
    from mt5desk import decision_core as dc
    # The gateway (MetaTrader5-only, not importable here) re-exports the same constant.
    gw_src = (Path(dc.__file__).parent / "gateway.py").read_text("utf-8")
    assert "E8_GOLD_SEND_GRACE_MIN as E8_GOLD_SEND_GRACE_MIN" in gw_src
    assert dc.E8_GOLD_SEND_GRACE_MIN == 10.0
    limit, basis = ff.e8_stale_limit_s()
    assert limit == 540.0 and "300s" in basis
    monkeypatch.setattr(dc, "E8_GOLD_SEND_GRACE_MIN", 12.0)       # read at call time
    assert ff.e8_stale_limit_s()[0] == 660.0
    for bad in ("x", float("nan"), 3.0):
        monkeypatch.setattr(dc, "E8_GOLD_SEND_GRACE_MIN", bad)
        assert ff.e8_stale_limit_s()[0] == 300.0


@pytest.mark.parametrize(("age_s", "places"), [(530, True), (550, False)])
def test_an_e8_report_older_than_the_bound_is_refused_and_billed(world, age_s: int,
                                                                 places: bool) -> None:
    world.report.write_text(json.dumps(_e8_report(at=NOW - timedelta(seconds=age_s))), "utf-8")
    mt5 = _MT5()
    doc = _pass(mt5)
    if places:
        assert doc["follow"]["action"] == "follow" and len(_entries(mt5)) == 1
        return
    assert mt5.sent == [] and doc["follow"]["action"] == "e8_stale"
    assert "limit 540s" in doc["follow"]["why"]
    (row,) = [r for r in _rows() if r.get("status") == "RAIL_BLOCKED"]
    assert row["reason"] == "e8_stale" and row["rail"] == ff.RAIL
    assert row["missed_growth_risk_usd"] == doc["planned_usd"] and doc["planned_usd"] > 0


def test_an_e8_gold_state_past_the_bound_but_inside_the_oco_bound_is_refused(world) -> None:
    """545 s: the OCO's own 600 s bound would still read it; the follower does not."""
    oco.publish_lane("e8", world.e8_key, positions=[{"id": E8_POS, "side": "long",
                                                     "opened_date": DAY}],
                     orders=[], date=DAY, now=datetime.now(tz=UTC) - timedelta(seconds=545))
    assert oco.read_lane("e8")[0] is not None
    mt5 = _MT5()
    doc = _pass(mt5)
    assert mt5.sent == [] and doc["follow"]["action"] == "e8_stale"


def test_missed_growth_bills_the_stale_e8_refusal(world, monkeypatch) -> None:
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "FTMO_INTENTS", Path(ff.INTENTS))
    world.report.write_text(json.dumps(_e8_report(at=NOW - timedelta(minutes=11))), "utf-8")
    doc = _pass(_MT5())
    line = mg.published_ftmo_follower_lines()["rails"]["ftmo_follower"]
    assert line["by_reason"] == {"e8_stale": 1}
    assert line["undeployed_risk_usd"] == doc["planned_usd"] and line["n_unpriced"] == 0


# ======================================================================== the twin-cancel mirror

@pytest.mark.parametrize("change", ["e8_stands_down", "e8_position_gone", "e8_unreadable"])
def test_the_resting_ftmo_order_is_cancelled_when_e8_no_longer_shows_a_live_fill(
        world, change: str) -> None:
    mt5 = _MT5()
    _pass(mt5)
    (resting,) = mt5.orders
    if change == "e8_stands_down":
        world.report.write_text(json.dumps(_e8_report(guard="BREACHED: no new placements")),
                                "utf-8")
    elif change == "e8_position_gone":
        oco.publish_lane("e8", world.e8_key, positions=[], orders=[], date=DAY)
    else:
        world.report.unlink()
    _pass(mt5, now=NOW + timedelta(minutes=1))
    removes = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_REMOVE]
    assert [r["order"] for r in removes] == [resting.ticket] and mt5.orders == []
    assert len(_entries(mt5)) == 1                               # and never a second order


def _cancel_bills() -> list[dict]:
    return [r for r in _rows() if r.get("status") == "RAIL_BLOCKED"
            and str(r.get("reason") or "").startswith("cancel_")]


def test_a_stale_e8_cancel_is_billed_with_the_orders_risk_once_per_window_per_day(
        world, monkeypatch) -> None:
    """v2s MF-B: the resting entry cancelled on `e8_stale` is risk held back. The "one order"
    step writes nothing while an own order exists, so the cancel itself is the bill: one
    RAIL_BLOCKED row at the cancelled order's own risk (volume x |price - sl| x contract)."""
    mt5 = _MT5()
    _pass(mt5)
    (resting,) = mt5.orders
    risk = round(resting.volume_current * abs(resting.price_open - resting.sl) * 100.0, 2)
    assert risk > 0
    later = NOW + timedelta(minutes=10)                     # E8's report is 600 s old > 540 s
    doc = _pass(mt5, now=later)
    assert doc["follow"]["action"] == "e8_stale"
    assert [r["order"] for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_REMOVE] == [
        resting.ticket]
    (row,) = _cancel_bills()
    assert row["rail"] == ff.RAIL and row["reason"] == "cancel_e8_stale"
    assert row["order_id"] == resting.ticket and row["missed_growth_risk_usd"] == risk
    # Once per window per day: further stale passes add no second bill (and no order).
    _pass(mt5, now=later + timedelta(minutes=1))
    assert len(_cancel_bills()) == 1 and len(_entries(mt5)) == 1
    # ... and missed_growth reads it on the follower's own line.
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "FTMO_INTENTS", Path(ff.INTENTS))
    line = mg.published_ftmo_follower_lines()["rails"][ff.RAIL]
    assert line["by_reason"].get("cancel_e8_stale") == 1
    assert line["undeployed_risk_usd"] >= risk


@pytest.mark.parametrize("change", ["e8_position_gone", "e8_unreadable"])
def test_every_e8_driven_cancel_is_billed(world, change: str) -> None:
    mt5 = _MT5()
    _pass(mt5)
    (resting,) = mt5.orders
    if change == "e8_position_gone":
        oco.publish_lane("e8", world.e8_key, positions=[], orders=[], date=DAY)
    else:
        world.report.unlink()
    _pass(mt5, now=NOW + timedelta(minutes=1))
    (row,) = _cancel_bills()
    assert row["order_id"] == resting.ticket and row["missed_growth_risk_usd"] > 0


def test_a_session_end_cancel_is_not_a_refusal_and_is_not_billed(world) -> None:
    mt5 = _MT5()
    _pass(mt5)
    mt5.tick = int((NOW + timedelta(hours=3 + 5)).timestamp())   # 13:30 server: session over
    # E8 is current (its report rewritten this pass), so the session end alone cancels.
    world.report.write_text(json.dumps(_e8_report(at=NOW + timedelta(hours=5))), "utf-8")
    oco.publish_lane("e8", world.e8_key,
                     positions=[{"id": E8_POS, "side": "long", "opened_date": DAY}], orders=[],
                     date=DAY)
    doc = _pass(mt5, now=NOW + timedelta(hours=5))
    assert doc["follow"]["action"] == "follow"
    assert mt5.orders == [] and _cancel_bills() == []


def test_the_cancel_touches_only_this_lanes_magic(world) -> None:
    """A foreign (manual or other-EA) gold order on the FTMO account is never removed, even when
    E8 goes stale -- the follower's cancel is MAGIC 341955 only."""
    assert ff.MAGIC == 341955
    mt5 = _MT5()
    _pass(mt5)
    mt5.orders.append(SimpleNamespace(ticket=4242, symbol="XAUUSD", type=mt5.ORDER_TYPE_BUY_STOP,
                                      magic=777, price_open=4345.0, sl=4325.0,
                                      volume_current=0.5, time_setup=mt5.tick))
    _pass(mt5, now=NOW + timedelta(minutes=10))
    removed = [r["order"] for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_REMOVE]
    assert 4242 not in removed and any(o.ticket == 4242 for o in mt5.orders)


def test_the_follower_gate_and_send_run_under_the_placement_lock(world, monkeypatch) -> None:
    """v2s SF-2: the gate (and the send after it) run while this process holds the one
    cross-account placement lock, and the lane state is republished before it is released."""
    held: list[bool] = []
    real_gate = oco.gate

    def gate(*a: Any, **k: Any) -> Any:
        held.append(any(v > 0 for v in xa._HELD.values()))
        return real_gate(*a, **k)

    monkeypatch.setattr(ff._oco, "gate", gate)
    mt5 = _MT5()
    real_send = mt5.order_send
    sent_held: list[bool] = []

    def send(req: dict) -> Any:
        sent_held.append(any(v > 0 for v in xa._HELD.values()))
        return real_send(req)

    mt5.order_send = send  # type: ignore[method-assign]
    doc = _pass(mt5)
    assert held == [True] and sent_held == [True] and len(_entries(mt5)) == 1
    assert doc["gold_oco"]["republished_after_send"] is True
    st, why = oco.read_lane("ftmo")
    assert st is not None, why
    assert [o["side"] for o in st["orders"]] == ["long"]          # the resting order, published


def test_the_follower_re_reads_every_lane_at_decision_time(world) -> None:
    """v2s SF-2: a Fusion short that lands after the pass's first reading -- but before the
    decision -- is seen by the gate under the lock: nothing is sent and the refusal is billed."""
    mt5 = _MT5()
    real = mt5.positions_get
    fired: list[bool] = []

    def positions_get(symbol: str | None = None) -> list:
        if any(v > 0 for v in xa._HELD.values()) and not fired:
            fired.append(True)        # inside the placement lock: Fusion just sold gold
            oco.publish_lane("fusion", oco.oco_account_key(72345678, "FusionMarkets-Test"),
                             positions=[{"id": 1, "side": "short", "opened_date": DAY}],
                             orders=[], date=DAY)
        return real(symbol)

    mt5.positions_get = positions_get  # type: ignore[method-assign]
    doc = _pass(mt5)
    assert fired and _entries(mt5) == []
    assert any(sk["reason"] == "gold_oco" and "fusion holds an open gold short" in sk["why"]
               for sk in doc["skipped"])
    assert any(r.get("reason") == "gold_oco" and r["status"] == "RAIL_BLOCKED"
               and r["missed_growth_risk_usd"] is not None for r in _rows())


def test_the_resting_order_dies_with_the_asia_session(world) -> None:
    mt5 = _MT5()
    _pass(mt5)
    mt5.tick = int((NOW + timedelta(hours=3 + 5)).timestamp())   # 13:30 server: session over
    _pass(mt5, now=NOW + timedelta(hours=5))
    assert mt5.orders == []


# ======================================================================== account and arming

@pytest.mark.parametrize("bad", ["login", "server", "trade_mode", "no_file"])
def test_an_account_mismatch_does_nothing_at_all(world, bad: str) -> None:
    kw: dict[str, Any] = {}
    if bad == "login":
        kw["login"] = 11111111
    elif bad == "server":
        kw["server"] = "FTMO-Demo"
    elif bad == "trade_mode":
        kw["trade_mode"] = 2
    else:
        world.acct.unlink()
    mt5 = _MT5(**kw)
    doc = _pass(mt5)
    assert doc["status"] == "ACCOUNT_REFUSED" and mt5.sent == []
    assert str(FT_LOGIN) not in json.dumps(doc) and str(11111111) not in json.dumps(doc)


def test_without_the_armed_marker_the_lane_is_standby(world, monkeypatch) -> None:
    world.tmp.joinpath("FTMO_FOLLOWER_ARMED").unlink()
    armed = ff.ARMED_MARKER.exists()
    mt5 = _MT5()
    doc = _pass(mt5, armed=armed)
    assert armed is False and mt5.sent == []
    assert doc["placed"] and doc["placed"][0]["shadow"] is True
    assert [r["status"] for r in _rows()] == ["WOULD_PLACE"]


@pytest.mark.parametrize("cert", [{"enabled": True, "e8": {"gold_asia": 0.0095}},
                                  {"enabled": False, "ftmo": {"gold_asia": 0.009}},
                                  {"enabled": True, "ftmo": {"gold_asia": "high"}},
                                  {"enabled": True, "ftmo": {"gold_asia": 0.0}},
                                  {"enabled": True, "ftmo": {}}])
def test_a_void_ftmo_block_places_nothing(world, cert: dict) -> None:
    world.cert.write_text(json.dumps(cert), "utf-8")
    mt5 = _MT5()
    _pass(mt5)
    assert mt5.sent == [] and any(r.get("reason") == "cert_void" for r in _rows())


def test_the_shipped_cert_book_funds_ftmo_gold_asia_at_0009() -> None:
    from mt5desk.kelly_sizing import CERT_BOOK_FILE, load_cert_book
    assert load_cert_book(CERT_BOOK_FILE, "ftmo") == {"gold_asia": 0.009}


# ======================================================================== FTMO's own rules

def test_a_trade_that_could_breach_the_daily_loss_is_refused(world) -> None:
    # 4,000 lost since midnight CET: 4,000 + (20 + 24.13 slip) x 0.45 x 100 = 5,985.85 >= 5,000.
    mt5 = _MT5(deals=(SimpleNamespace(profit=-4000.0, commission=0.0, swap=0.0, fee=0.0),))
    doc = _pass(mt5)
    assert _entries(mt5) == []
    (row,) = [r for r in _rows() if r.get("reason") == "loss_guard"]
    assert "daily loss" in row["why"] and row["missed_growth_risk_usd"] == 900.0
    assert "24.13" in doc["skipped"][0]["why"]


def test_the_slip_allowance_and_the_max_loss_floor() -> None:
    assert ff.trade_risk(0.45, 20.0, 100.0) == pytest.approx(1985.85)
    assert ff.loss_guard(100_000, 100_000, 100_000, 1985.85)[0]
    assert not ff.loss_guard(100_000, 100_000, 91_000, 1985.85)[0]          # 10% floor
    assert not ff.loss_guard(100_000, 103_100, 100_000, 1985.85)[0]         # 5% daily


def test_unreadable_deal_history_refuses(world) -> None:
    mt5 = _MT5()
    mt5.deals = None  # type: ignore[assignment]
    _pass(mt5)
    assert _entries(mt5) == []


def test_no_new_entry_within_two_hours_of_the_market_close(world) -> None:
    late = datetime(2026, 10, 21, 19, 30, tzinfo=UTC)            # 15:30 New York
    assert ff.near_market_close(late) and not ff.near_market_close(NOW)
    world.report.write_text(json.dumps(_e8_report(at=late)), "utf-8")
    mt5 = _MT5(tick=int((late - timedelta(hours=12)).timestamp()))  # server hour still in asia
    _pass(mt5, now=late)
    assert _entries(mt5) == [] and any(r.get("reason") == "gap_guard" for r in _rows())


def test_the_daily_request_budget_stops_new_risk(world) -> None:
    ff.STATE.write_text(json.dumps({"date": DAY, "windows": {}, "logged": {},
                                    "requests": {DAY: ff.REQUEST_BUDGET}}), "utf-8")
    mt5 = _MT5()
    _pass(mt5)
    assert mt5.sent == []
    assert [r["status"] for r in _rows() if r.get("status") != "SKIPPED"] == ["REJECTED"]


def test_e8s_ratchet_is_mirrored_and_the_close_hour_closes(world) -> None:
    mt5 = _MT5(bid=4350.0, ask=4350.2)
    mt5.positions = [SimpleNamespace(ticket=9001, symbol="XAUUSD", type=0, magic=ff.MAGIC,
                                     volume=0.45, sl=4320.0, tp=4380.0, time=TICK)]
    world.report.write_text(json.dumps(_e8_report(actions=[
        {"act": "ratchet_stop", "position_id": E8_POS, "before": 4320.0, "after": 4335.0,
         "ok": True}])), "utf-8")
    ff.STATE.write_text(json.dumps({"date": DAY, "logged": {}, "requests": {}, "windows": {
        "asia": {"placed_hour": 8.5, "e8_position_id": str(E8_POS)}}}), "utf-8")
    _pass(mt5)
    (sltp,) = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_SLTP]
    assert sltp["sl"] == 4335.0 and sltp["position"] == 9001 and _entries(mt5) == []
    mt5.tick = int((NOW + timedelta(hours=3 + 11)).timestamp())  # 19:30 server
    _pass(mt5, now=NOW + timedelta(hours=11))
    (close,) = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_DEAL]
    assert close["position"] == 9001 and close["type"] == mt5.ORDER_TYPE_SELL


def test_the_ftmo_lane_publishes_a_keyed_gold_state_and_never_its_login(world) -> None:
    mt5 = _MT5()
    _pass(mt5)
    st, why = oco.read_lane("ftmo")
    assert st is not None, why
    assert st["account_key"] == oco.oco_account_key(FT_LOGIN, FT_SERVER)
    blobs = [f.read_text("utf-8", errors="replace") for d in (world.tmp, xa.XACCT_DIR)
             for f in d.iterdir() if f.is_file()
             and f.name not in ("FTMO_LIVE_ACCOUNT.json", "racer.py")]
    assert not any(str(FT_LOGIN) in b for b in blobs)


def test_main_refuses_outside_an_interactive_desktop_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ff, "LOG", tmp_path / "log")
    monkeypatch.setenv("SSH_CONNECTION", "10.0.0.1 1 10.0.0.2 22")
    monkeypatch.setitem(sys.modules, "MetaTrader5", SimpleNamespace(
        initialize=lambda **kw: pytest.fail("initialize must not be reached")))
    assert ff.main([]) == 1
    ok, why = ff.interactive_session()
    assert not ok and "SSH" in why


# ======================================================================== v2: idempotency

def _stopped_out(mt5: _MT5) -> None:
    """FTMO's order filled and was stopped: the book is flat, the MAGIC order and its deals are
    on today's history (as MT5 keeps them)."""
    (o,) = mt5.orders
    mt5.orders = []
    mt5.hist_orders.append(SimpleNamespace(ticket=o.ticket, symbol="XAUUSD", magic=ff.MAGIC,
                                           time_setup=mt5.tick, type=o.type))
    mt5.deals = (SimpleNamespace(ticket=1, symbol="XAUUSD", magic=ff.MAGIC, time=mt5.tick + 60,
                                 profit=-900.0, commission=0.0, swap=0.0, fee=0.0),)


@pytest.mark.parametrize("damage", ["lost", "torn"])
def test_a_lost_or_torn_state_after_a_stop_out_never_sends_a_second_order(
        world, damage: str) -> None:
    """The audit's probe (v1 must-fix 5): FTMO fills and is stopped out, the state is lost or
    torn, E8 is still open -> v1 sent a second order. The MAGIC history now decides."""
    mt5 = _MT5()
    _pass(mt5)
    assert len(_entries(mt5)) == 1
    _stopped_out(mt5)
    if damage == "lost":
        Path(ff.STATE).unlink()
    else:
        Path(ff.STATE).write_text('{"date": "2026-10-21", "windows": {', "utf-8")
    doc = _pass(mt5, now=NOW + timedelta(minutes=2))
    assert len(_entries(mt5)) == 1
    assert any(s["reason"] == "already_followed" for s in doc["skipped"])
    if damage == "torn":
        assert "state_unreadable" in doc


def test_the_same_e8_fill_is_never_followed_twice_even_on_a_new_day(world) -> None:
    mt5 = _MT5()
    _pass(mt5)
    st = json.loads(Path(ff.STATE).read_text("utf-8"))
    assert str(E8_POS) in st["followed"]
    # A new server day with an empty FTMO history: only the followed key stops a repeat.
    st["date"] = "2026-10-20"
    Path(ff.STATE).write_text(json.dumps(st), "utf-8")
    mt5.orders = []
    doc = _pass(mt5, now=NOW + timedelta(minutes=2))
    assert len(_entries(mt5)) == 1 and any(s["reason"] == "already_followed"
                                           for s in doc["skipped"])


def test_an_unreadable_history_places_nothing_and_bills_it(world, monkeypatch) -> None:
    mt5 = _MT5()
    monkeypatch.setattr(mt5, "history_orders_get", lambda since, until: None)
    _pass(mt5)
    assert _entries(mt5) == []
    (row,) = [r for r in _rows() if r.get("reason") == "history_unreadable"]
    assert row["status"] == "RAIL_BLOCKED" and row["missed_growth_risk_usd"] == 900.0


def test_the_follow_is_written_ahead_of_the_send(world, monkeypatch) -> None:
    mt5 = _MT5()
    seen: list[dict] = []

    def send(req: dict) -> SimpleNamespace:
        seen.append(json.loads(Path(ff.STATE).read_text("utf-8")))
        raise ConnectionError("the reply was lost")
    monkeypatch.setattr(mt5, "order_send", send)
    _pass(mt5)
    assert seen and str(E8_POS) in seen[0]["followed"]
    assert seen[0]["windows"]["asia"]["status"] == "SENDING"


def test_the_state_write_is_atomic_and_retries_a_windows_permission_error(
        world, monkeypatch) -> None:
    calls: list[str] = []
    real = ff.os.replace

    def flaky(src: Any, dst: Any) -> None:
        calls.append(str(dst))
        if len(calls) <= 2:
            raise PermissionError("a reader holds the destination open")
        real(src, dst)
    synced: list[int] = []
    real_fsync = ff.os.fsync
    monkeypatch.setattr(ff.os, "replace", flaky)
    monkeypatch.setattr(ff.os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd))[1])
    monkeypatch.setattr(ff.time, "sleep", lambda s: None)
    ff._atomic_write(Path(ff.STATE), '{"ok": true}')
    assert json.loads(Path(ff.STATE).read_text("utf-8")) == {"ok": True}
    assert len(calls) == 3 and synced
    assert not list(Path(ff.STATE).parent.glob("*.tmp"))


# ======================================================================== v2: account type

def test_an_undeclared_account_type_binds_nothing(world) -> None:
    doc = json.loads(world.acct.read_text("utf-8"))
    doc.pop("account_type")
    world.acct.write_text(json.dumps(doc), "utf-8")
    mt5 = _MT5()
    out = _pass(mt5)
    assert out["status"] == "ACCOUNT_REFUSED" and "account_type" in out["why"]
    assert mt5.sent == []


@pytest.mark.parametrize(("kind", "placed"), [("2-step", True), ("1-step", False)])
def test_the_daily_limit_is_the_account_types(world, kind: str, placed: bool) -> None:
    """Today's loss 2,000 + this trade (0.45 lot x (20 + 24.13) pt x 100 = 1,985.85) is under
    2-Step's 5,000 and over 1-Step's 3,000."""
    doc = json.loads(world.acct.read_text("utf-8"))
    doc["account_type"] = kind
    world.acct.write_text(json.dumps(doc), "utf-8")
    mt5 = _MT5(equity=98_000.0, balance=98_000.0,
               deals=(SimpleNamespace(symbol="EURUSD", magic=0, time=TICK - 3600,
                                      profit=-2000.0, commission=0.0, swap=0.0, fee=0.0),))
    out = _pass(mt5)
    assert bool(_entries(mt5)) is placed
    assert (f"{ff.ACCOUNT_TYPES[kind]:.0%} daily limit") in out["loss_guard"]
    assert ff.ACCOUNT_TYPES == {"2-step": 0.05, "1-step": 0.03}


# ======================================================================== v2: the lot cap

def test_a_narrow_stop_is_capped_and_the_clip_is_billed(world) -> None:
    rep = _e8_report()
    rep["state"]["windows"]["asia"]["orders"]["buy_stop"].update({"sl": 4337.0})   # 3-pt stop
    world.report.write_text(json.dumps(rep), "utf-8")
    mt5 = _MT5()
    _pass(mt5)
    (req,) = _entries(mt5)
    cap = int(ff.MAX_NOTIONAL_X * 100_000 / (4340.0 * 100.0) / 0.01 + 1e-9) * 0.01
    assert req["volume"] == pytest.approx(cap) and req["volume"] < 3.0     # uncapped: 3.0 lots
    (row,) = [r for r in _rows() if r.get("rail") == ff.LOT_CAP_RAIL]
    assert row["status"] == "RAIL_BLOCKED" and row["lot_uncapped"] == pytest.approx(3.0)
    assert row["missed_growth_risk_usd"] == pytest.approx((3.0 - cap) * 3.0 * 100.0, abs=0.01)


def test_a_declared_max_lot_caps_tighter(world) -> None:
    doc = json.loads(world.acct.read_text("utf-8"))
    doc["max_lot"] = 0.2
    world.acct.write_text(json.dumps(doc), "utf-8")
    mt5 = _MT5()
    _pass(mt5)
    (req,) = _entries(mt5)
    assert req["volume"] == pytest.approx(0.2)


def test_missed_growth_publishes_the_followers_rails(world, monkeypatch) -> None:
    from research import missed_growth as mg
    monkeypatch.setattr(mg, "FTMO_INTENTS", Path(ff.INTENTS))
    mt5 = _MT5()
    mt5.positions = [SimpleNamespace(ticket=42, symbol="XAUUSD", type=1, magic=0, volume=0.1,
                                     sl=0.0, tp=0.0, time=TICK)]
    _pass(mt5)                                                   # opposite_exposure, billed
    out = mg.published_ftmo_follower_lines()["rails"]
    line = out["ftmo_follower"]
    assert line["n"] == 1 and line["by_reason"] == {"opposite_exposure": 1}
    assert line["undeployed_risk_usd"] == 900.0 and line["n_unpriced"] == 0
    assert out["ftmo_lot_cap"]["verdict"] == mg.NOT_BINDING
    Path(ff.INTENTS).write_text("{torn", "utf-8")
    assert mg.published_ftmo_follower_lines()["unreadable"] == [Path(ff.INTENTS).name]


# ======================================================================== v2: flatten, page

def test_an_own_ftmo_fill_against_the_direction_is_flattened_at_once(world) -> None:
    mt5 = _MT5()
    mt5.positions = [SimpleNamespace(ticket=55, symbol="XAUUSD", type=1, magic=ff.MAGIC,
                                     volume=0.45, sl=4320.0, tp=4260.0, time=TICK)]
    doc = _pass(mt5)
    (close,) = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_DEAL]
    assert close["position"] == 55 and close["type"] == mt5.ORDER_TYPE_BUY
    assert any("against today's direction" in a for a in doc["alerts"])


def test_a_missing_hmac_key_pages(world, monkeypatch, tmp_path) -> None:
    from libs.ops import provenance as p
    monkeypatch.setenv(p.KEY_ENV, str(tmp_path / "absent.hmac"))
    mt5 = _MT5()
    doc = _pass(mt5)
    assert doc["status"] == "ACCOUNT_REFUSED" and mt5.sent == []
    assert doc["page"]["sent"] is True
    assert oco.PAGES and "ftmo" in oco.PAGES[-1][0] and str(FT_LOGIN) not in str(oco.PAGES)


# ======================================================================== v2: the prop fills ledger

def _closed_trade(mt5: _MT5, *, pid: int = 9101) -> None:
    """An FTMO long that entered at 4340.4 and was stopped at 4319.8, on the MAGIC history."""
    mt5.hist_orders.append(SimpleNamespace(ticket=pid, symbol="XAUUSD", magic=ff.MAGIC,
                                           time_setup=TICK, type=4, price_open=4340.0,
                                           sl=4320.0, tp=4380.0))
    mt5.deals = (
        SimpleNamespace(ticket=1, order=pid, position_id=pid, symbol="XAUUSD", magic=ff.MAGIC,
                        entry=0, type=0, volume=0.45, price=4340.4, time=TICK + 60, profit=0.0,
                        commission=-3.5, swap=0.0, fee=0.0, reason=0),
        SimpleNamespace(ticket=2, order=pid + 1, position_id=pid, symbol="XAUUSD",
                        magic=ff.MAGIC, entry=1, type=1, volume=0.45, price=4319.8,
                        time=TICK + 600, profit=-927.0, commission=-3.5, swap=0.0, fee=0.0,
                        reason=4),
        SimpleNamespace(ticket=3, order=77, position_id=4242, symbol="XAUUSD", magic=0,
                        entry=0, type=1, volume=1.0, price=4300.0, time=TICK, profit=0.0))


def _ledger() -> list[dict]:
    p = Path(ff.PROP_LEDGER)
    return [json.loads(ln) for ln in p.read_text("utf-8").splitlines() if ln.strip()] \
        if p.exists() else []


def test_a_closed_ftmo_position_lands_in_the_prop_fills_ledger_once(world) -> None:
    mt5 = _MT5()
    _closed_trade(mt5)
    doc = _pass(mt5)
    assert doc["fills_ledger"]["written"] == 1
    _pass(mt5, now=NOW + timedelta(minutes=1))                   # deduped by ftmo:<position>
    (row,) = _ledger()
    assert row["schema"] == "prop-fills-v1" and row["book"] == "ftmo"
    assert f"{row['book']}:{row['position_id']}" == "ftmo:9101"
    assert (row["entry_side"], row["side"], row["entry_price"], row["fill_price"]) == (
        0, 1, 4340.4, 4319.8)
    assert (row["sl"], row["tp"], row["intended_entry"]) == (4320.0, 4380.0, 4340.0)
    assert row["exit_reason"] == "stop" and row["pl_quote"] == -927.0
    assert row["r_multiple"] == pytest.approx(-20.6 / 20.4, abs=1e-4)
    # v2r fix 1: the fees are READ off the position's MT5 deals (entry + exit), a measured 0.0
    # included, and the net result follows from them.
    assert (row["commission"], row["swap"], row["fees"]) == (-7.0, 0.0, 0.0)
    assert row["fees_status"] == "MEASURED"
    assert row["fees_measured"] == ["commission", "swap", "fees"]
    assert row["pl_net_quote"] == -934.0
    assert xa.valid_key(row["account_key"])
    assert row["account_key"] == oco.oco_account_key(FT_LOGIN, FT_SERVER)
    text = Path(ff.PROP_LEDGER).read_text("utf-8")
    assert str(FT_LOGIN) not in text and FT_SERVER not in text
    assert not any(k in row for k in ff.PROP_BANNED)


def test_an_open_position_is_not_written_and_a_ledger_failure_costs_no_order(
        world, monkeypatch) -> None:
    mt5 = _MT5()
    _closed_trade(mt5)
    mt5.positions = [SimpleNamespace(ticket=9101, symbol="XAUUSD", type=0, magic=ff.MAGIC,
                                     volume=0.45, sl=4320.0, tp=4380.0, time=TICK)]
    assert _pass(mt5)["fills_ledger"]["written"] == 0 and _ledger() == []
    mt5.positions = []
    monkeypatch.setattr(ff, "append_fills", lambda rows, path=None: 1 / 0)
    doc = _pass(mt5, now=NOW + timedelta(minutes=1))
    assert "ZeroDivisionError" in doc["fills_ledger"]["why"] and doc["status"] == "OK"


def test_a_fee_the_deal_does_not_carry_is_null_with_its_reason(world) -> None:
    """A deal with no `fee` (an older terminal build) keeps the fee null and says so; the fields
    it does carry are still measured, and the row is written."""
    mt5 = _MT5()
    _closed_trade(mt5)
    mt5.deals = tuple(SimpleNamespace(**{k: v for k, v in vars(d).items() if k != "fee"})
                      for d in mt5.deals)
    assert _pass(mt5)["fills_ledger"]["written"] == 1
    (row,) = _ledger()
    assert row["fees"] is None and (row["commission"], row["swap"]) == (-7.0, 0.0)
    assert row["fees_status"].startswith("PARTIAL") and "fee (2 of 2 deals" in row[
        "fees_status"]
    assert row["fees_measured"] == ["commission", "swap"] and row["pl_net_quote"] is None


def test_a_fee_not_read_off_the_deal_is_refused() -> None:
    with pytest.raises(ValueError, match=r"never 0\.0"):
        ff.append_fills([{"book": "ftmo", "position_id": 1, "commission": -3.5,
                          "fees_measured": ["swap"]}])


@pytest.mark.parametrize("field", ["login", "account", "username", "account_id"])
def test_the_ledger_refuses_a_login_field_and_a_zero_fee(world, field: str) -> None:
    with pytest.raises(ValueError, match=field):
        ff.append_fills([{"book": "ftmo", "position_id": 1, field: "x"}])
    with pytest.raises(ValueError, match=r"never 0\.0"):
        ff.append_fills([{"book": "ftmo", "position_id": 1, "commission": 0.0}])
    assert _ledger() == []


_WRITER = """
import sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from pathlib import Path
from prop import ftmo_follower as ff
book, base = sys.argv[4], int(sys.argv[5])
path = Path(sys.argv[3])
for i in range(150):
    row = {"schema": "prop-fills-v1", "book": book, "position_id": base + i, "pad": "x" * 900}
    if book == "ftmo":
        ff.append_fills([row], path)
    else:   # E8's writer: one line per write on an O_APPEND descriptor, as fills_ledger does
        import json, os
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        os.write(fd, (json.dumps(row) + "\\n").encode())
        os.close(fd)
"""


def test_two_writers_never_tear_a_line(world, tmp_path) -> None:
    import subprocess
    script = tmp_path / "writer.py"
    script.write_text(_WRITER, "utf-8")
    path = tmp_path / "shared_prop_ledger.jsonl"
    procs = [subprocess.Popen([sys.executable, str(script), str(_DESK), str(_DESK.parent.parent),
                               str(path), book, str(base)])
             for book, base in (("ftmo", 1000), ("e8", 5000))]
    assert all(p.wait(timeout=120) == 0 for p in procs)
    rows = [json.loads(ln) for ln in path.read_text("utf-8").splitlines()]
    assert len(rows) == 300
    assert {f"{r['book']}:{r['position_id']}" for r in rows} == (
        {f"ftmo:{1000 + i}" for i in range(150)} | {f"e8:{5000 + i}" for i in range(150)})
