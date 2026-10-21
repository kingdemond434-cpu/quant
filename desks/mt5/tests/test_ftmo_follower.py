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
E8_LOGIN = 81234567                                      # fake
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

    def order_send(self, req: dict) -> SimpleNamespace:
        self.sent.append(req)
        ticket = 9000 + len(self.sent)
        if req["action"] == self.TRADE_ACTION_PENDING:
            self.orders.append(SimpleNamespace(ticket=ticket, symbol="XAUUSD", type=req["type"],
                                               magic=req["magic"], price_open=req["price"]))
        if req["action"] == self.TRADE_ACTION_REMOVE:
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
    for name in ("STATE", "OUT", "INTENTS", "LOG"):
        monkeypatch.setattr(ff, name, tmp_path / f"{name.lower()}.json")
    acct = tmp_path / "FTMO_LIVE_ACCOUNT.json"
    acct.write_text(json.dumps({"login": FT_LOGIN, "server": FT_SERVER, "trade_mode": 0,
                                "initial_balance": 100_000.0}), "utf-8")
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
    e8k = oco.oco_account_key(E8_LOGIN, "tradelocker")
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
    assert mt5.sent == [] and doc["follow"]["action"] == "unreadable"
    (row,) = [r for r in _rows() if r.get("status") == "RAIL_BLOCKED"]
    assert row["rail"] == ff.RAIL and row["reason"] == "unreadable" and row["why"]


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
