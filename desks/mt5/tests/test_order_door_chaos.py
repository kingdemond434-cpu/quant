"""CHAOS LAB for the one door for money (`mt5desk.order_door`).

The broker is faked (MetaTrader5 installs only on Windows) and made to fail every way a live
terminal has failed or can: `order_send` returning None, a requote, TRADE_RETCODE_REJECT from the
check and from the send, a timeout raised mid-send, a disconnect in the middle of a close, and a
restart while a position is held -- with its stop lost. Each test asserts the three things the
door promises: it REFUSES what it must, it LOGS every attempt, and it NEVER sends twice.
"""
from __future__ import annotations

import ast
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import order_door as door  # noqa: E402

MAGIC = 341953


class FakeMT5:
    """The terminal, scripted. `send_plan` is a list of behaviours consumed one per send:
    a retcode int, None (the API returns nothing), or an Exception instance to raise. A
    successful placement is ALSO recorded on the venue (resting order / position), which is
    what a real terminal does even when the answer never reaches the caller."""

    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_MODIFY = 7
    TRADE_ACTION_REMOVE = 8
    TRADE_ACTION_CLOSE_BY = 10
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_STOP = 4
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    DEAL_ENTRY_IN = 0

    def __init__(self, send_plan: list[Any] | None = None, check_retcode: int | None = 0,
                 lands_anyway: bool = False) -> None:
        self.send_plan = list(send_plan or [])
        self.check_retcode = check_retcode
        self.lands_anyway = lands_anyway      # a failed/None/raised send that DID reach the venue
        self.sent: list[dict] = []
        self.checked: list[dict] = []
        self.orders: list[SimpleNamespace] = []
        self.positions: list[SimpleNamespace] = []
        self.deals: list[SimpleNamespace] = []
        self._ticket = 1000
        self.bid, self.ask = 2000.0, 2000.5

    # ---- venue reads
    def orders_get(self, symbol: str | None = None, **_: Any):
        return tuple(o for o in self.orders if symbol is None or o.symbol == symbol)

    def positions_get(self, symbol: str | None = None, ticket: int | None = None, **_: Any):
        return tuple(p for p in self.positions
                     if (symbol is None or p.symbol == symbol)
                     and (ticket is None or p.ticket == ticket))

    def history_deals_get(self, *_: Any, **__: Any):
        return tuple(self.deals)

    def symbol_info_tick(self, symbol: str):
        return SimpleNamespace(bid=self.bid, ask=self.ask, time=0)

    def last_error(self):
        return (-10005, "IPC timeout")

    # ---- the broker
    def order_check(self, req: dict):
        self.checked.append(dict(req))
        if self.check_retcode is None:
            return None
        return SimpleNamespace(retcode=self.check_retcode, comment="checked")

    def _land(self, req: dict) -> int:
        self._ticket += 1
        t = self._ticket
        if req["action"] == self.TRADE_ACTION_PENDING:
            self.orders.append(SimpleNamespace(ticket=t, symbol=req["symbol"],
                                               comment=req.get("comment", ""),
                                               magic=req.get("magic", 0),
                                               price_open=req.get("price")))
        elif req["action"] == self.TRADE_ACTION_DEAL and not req.get("position"):
            self.positions.append(SimpleNamespace(
                ticket=t, symbol=req["symbol"], comment=req.get("comment", ""),
                magic=req.get("magic", 0), volume=req["volume"], type=req["type"],
                sl=req.get("sl", 0.0), tp=req.get("tp", 0.0), time=None))
        elif req["action"] == self.TRADE_ACTION_SLTP:
            for p in self.positions:
                if p.ticket == req["position"]:
                    p.sl = req["sl"]
        return t

    def order_send(self, req: dict):
        self.sent.append(dict(req))
        step = self.send_plan.pop(0) if self.send_plan else 10009
        if isinstance(step, BaseException):
            if self.lands_anyway:
                self._land(req)
            raise step
        if step is None:
            if self.lands_anyway:
                self._land(req)
            return None
        if step in (10008, 10009, 10010):
            t = self._land(req)
            vol = req.get("volume", 0.0)
            return SimpleNamespace(retcode=step, comment="done", order=t, deal=t + 50000,
                                   volume=(vol / 2 if step == 10010 else vol),
                                   price=req.get("price", 0.0))
        return SimpleNamespace(retcode=step, comment="no", order=0, deal=0, volume=0.0,
                               price=0.0)


@pytest.fixture(autouse=True)
def _isolated_door(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    door._MEMORY_IN_DOUBT.clear()
    yield
    door._MEMORY_IN_DOUBT.clear()


def _open(price: float = 2000.5, comment: str = "DWfam_eurusd") -> dict:
    return {"action": 1, "symbol": "XAUUSD", "volume": 0.02, "type": 0, "price": price,
            "sl": 1990.0, "tp": 2020.0, "deviation": 20, "magic": MAGIC, "comment": comment}


def _close(ticket: int = 7) -> dict:
    return {"action": 1, "symbol": "XAUUSD", "volume": 0.02, "type": 1, "position": ticket,
            "price": 2000.0, "deviation": 20, "magic": MAGIC}


def _rows() -> list[dict]:
    return door.read_ledger()


# ------------------------------------------------------------------ the happy path is logged
def test_every_attempt_is_checked_first_then_sent_once_and_ledgered() -> None:
    mt5 = FakeMT5()
    res = door.send(mt5, _open(), caller="t")
    assert res.retcode == 10009
    assert len(mt5.checked) == 1 and len(mt5.sent) == 1
    (row,) = _rows()
    assert row["kind"] == "open" and row["check"] == "pass" and row["retcode"] == 10009
    assert row["validation"] == "ok" and row["caller"] == "t"


# ------------------------------------------------------------------ order_send returns None
def test_none_from_order_send_is_in_doubt_and_the_resend_is_refused_when_it_landed() -> None:
    mt5 = FakeMT5(send_plan=[None], lands_anyway=True)
    assert door.send(mt5, _open()) is None
    assert _rows()[-1]["validation"] == "no_result" and _rows()[-1]["in_doubt"] is True
    again = door.send(mt5, _open(price=2001.0))      # the market moved; same order all the same
    assert isinstance(again, door.DoorRefused) and again.door_reason == "duplicate_of_in_doubt"
    assert len(mt5.sent) == 1, "a send in doubt that landed was sent twice"
    assert _rows()[-1]["reason"] == "duplicate_of_in_doubt"


def test_none_that_did_not_land_clears_and_the_next_send_goes() -> None:
    mt5 = FakeMT5(send_plan=[None, 10009], lands_anyway=False)
    assert door.send(mt5, _open()) is None
    res = door.send(mt5, _open())
    assert res.retcode == 10009 and len(mt5.sent) == 2
    assert door.load_in_doubt() == {}
    assert "did not land" in _rows()[-1]["in_doubt_resolved"]


def test_an_in_doubt_key_with_an_unreadable_venue_is_refused_not_guessed() -> None:
    mt5 = FakeMT5(send_plan=[None], lands_anyway=False)
    door.send(mt5, _open())
    for name in ("orders_get", "positions_get", "history_deals_get"):
        setattr(mt5, name, lambda *a, **k: None)
    res = door.send(mt5, _open())
    assert isinstance(res, door.DoorRefused)
    assert res.door_reason == "in_doubt_venue_unreadable" and len(mt5.sent) == 1


# ------------------------------------------------------------------ requote
def test_a_requote_is_reported_and_never_retried() -> None:
    mt5 = FakeMT5(send_plan=[10004])
    res = door.send(mt5, _open())
    assert res.retcode == 10004 and len(mt5.sent) == 1
    row = _rows()[-1]
    assert row["validation"] == "rejected" and row["retcode_name"] == "requote"
    assert door.load_in_doubt() == {}, "a clean rejection is not in doubt"


# ------------------------------------------------------------------ TRADE_RETCODE_REJECT
def test_a_broker_check_reject_refuses_new_risk_before_it_is_sent() -> None:
    mt5 = FakeMT5(check_retcode=10006)
    res = door.send(mt5, _open())
    assert isinstance(res, door.DoorRefused) and res.retcode == 10006
    assert mt5.sent == [], "the broker said no in the check; the door sent it anyway"
    assert _rows()[-1]["reason"] == "broker_check_rejected"


def test_a_reject_from_the_send_itself_is_returned_once() -> None:
    mt5 = FakeMT5(send_plan=[10006])
    res = door.send(mt5, _open())
    assert res.retcode == 10006 and len(mt5.sent) == 1
    assert _rows()[-1]["retcode_name"] == "reject"


@pytest.mark.parametrize("req", [_close(), {"action": 6, "symbol": "XAUUSD", "position": 7,
                                            "sl": 1995.0, "tp": 0.0, "magic": MAGIC},
                                 {"action": 8, "order": 55}])
def test_a_check_reject_never_blocks_a_close_a_stop_or_a_cancel(req: dict) -> None:
    mt5 = FakeMT5(check_retcode=10006)
    door.send(mt5, req)
    assert len(mt5.sent) == 1, "a pre-check blocked a risk-reducing action"
    assert _rows()[-1]["check"] == "reject" and _rows()[-1]["door"] == "sent"


def test_an_unavailable_check_is_unmeasured_and_the_send_proceeds() -> None:
    mt5 = FakeMT5(check_retcode=None)
    assert door.send(mt5, _open()).retcode == 10009
    assert _rows()[-1]["check"] == "unmeasured"


# ------------------------------------------------------------------ timeout
def test_a_timeout_propagates_is_logged_and_is_never_sent_twice() -> None:
    mt5 = FakeMT5(send_plan=[TimeoutError("IPC send timed out")], lands_anyway=True)
    with pytest.raises(TimeoutError):
        door.send(mt5, _open())
    row = _rows()[-1]
    assert row["outcome"] == "exception" and "TimeoutError" in row["error"]
    assert row["in_doubt"] is True
    res = door.send(mt5, _open())
    assert isinstance(res, door.DoorRefused) and len(mt5.sent) == 1


# ------------------------------------------------------------------ disconnect mid-close
def test_a_disconnect_mid_close_raises_through_the_door_and_is_ledgered() -> None:
    mt5 = FakeMT5(send_plan=[ConnectionError("terminal disconnected")])
    with pytest.raises(ConnectionError):
        door.send(mt5, _close())
    row = _rows()[-1]
    assert row["kind"] == "close" and row["outcome"] == "exception"
    assert len(mt5.sent) == 1
    # A close is never deduplicated: the next pass must be free to close what is still open.
    assert door.load_in_doubt() == {}
    door.send(mt5, _close())
    assert len(mt5.sent) == 2


# ------------------------------------------------------------------ validation
def test_a_partial_fill_and_a_priceless_done_are_named() -> None:
    mt5 = FakeMT5(send_plan=[10010])
    door.send(mt5, _open())
    row = _rows()[-1]
    assert row["validation"] == "partial" and any("of 0.02" in n for n in row["notes"])

    class _NoPrice(FakeMT5):
        def order_send(self, req: dict):
            self.sent.append(req)
            return SimpleNamespace(retcode=10009, comment="", order=1, deal=2,
                                   volume=req["volume"], price=0.0)
    door.send(_NoPrice(), _open())
    assert _rows()[-1]["validation"] == "anomaly"


def test_a_naked_open_is_flagged_but_not_vetoed() -> None:
    mt5 = FakeMT5()
    req = dict(_open(), sl=0.0)
    assert door.send(mt5, req).retcode == 10009
    assert _rows()[-1]["no_stop"] is True


# ------------------------------------------------------------------ restart holding a position
def test_restart_with_a_held_position_reconciles_restores_the_stop_and_never_duplicates() -> None:
    # Pass 1: the entry times out AFTER reaching the venue, and the process dies.
    mt5 = FakeMT5(send_plan=[TimeoutError("died mid-send")], lands_anyway=True)
    with pytest.raises(TimeoutError):
        door.send(mt5, _open())
    held = mt5.positions[0]
    held.sl = 0.0                                 # and the stop did not survive either
    door._MEMORY_IN_DOUBT.clear()                 # a new process: only the FILE remembers

    intents = [{"ticket": held.ticket, "sl": 1990.0, "symbol": "XAUUSD"}]
    rep = door.restart_reconcile(mt5, magic=MAGIC, armed=True, intents=intents)
    assert rep["verdict"] == "OK" and len(rep["positions"]) == 1
    assert rep["in_doubt"][0]["landed"], "the in-doubt entry was not matched to the venue"
    (fix,) = rep["stopless"]
    assert fix["action"] == "restored" and held.sl == 1990.0
    stop_sends = [r for r in mt5.sent if r["action"] == mt5.TRADE_ACTION_SLTP]
    assert len(stop_sends) == 1 and stop_sends[0]["position"] == held.ticket

    # Pass 2's lane, having lost its own mark, tries the same entry again: refused.
    res = door.send(mt5, _open())
    assert isinstance(res, door.DoorRefused)
    entries = [r for r in mt5.sent if r["action"] == 1 and not r.get("position")]
    assert len(entries) == 1 and len(mt5.positions) == 1


def test_restart_never_moves_a_stop_to_a_level_that_is_a_market_exit() -> None:
    mt5 = FakeMT5()
    mt5.positions.append(SimpleNamespace(ticket=9, symbol="XAUUSD", comment="x", magic=MAGIC,
                                         volume=0.02, type=0, sl=0.0, tp=0.0, time=None))
    rep = door.restart_reconcile(mt5, magic=MAGIC, armed=True,
                                 intents=[{"ticket": 9, "sl": 2005.0}])   # above the bid
    assert rep["stopless"][0]["action"].startswith("none")
    assert mt5.sent == []


def test_restart_is_shadow_when_unarmed_and_ignores_other_magics() -> None:
    mt5 = FakeMT5()
    mt5.positions += [SimpleNamespace(ticket=9, symbol="XAUUSD", comment="x", magic=MAGIC,
                                      volume=0.02, type=0, sl=0.0, tp=0.0, time=None),
                      SimpleNamespace(ticket=10, symbol="XAUUSD", comment="m", magic=1,
                                      volume=1.0, type=0, sl=0.0, tp=0.0, time=None)]
    rep = door.restart_reconcile(mt5, magic=MAGIC, armed=False,
                                 intents=[{"ticket": 9, "sl": 1990.0}])
    assert [p["ticket"] for p in rep["positions"]] == [9]
    assert rep["stopless"][0]["action"].startswith("shadow") and mt5.sent == []
    assert _rows()[-1]["kind"] == "restart_reconcile"


def test_restart_with_an_unreadable_venue_is_unmeasured_and_does_not_raise() -> None:
    mt5 = FakeMT5()

    def _boom(*a: Any, **k: Any):
        raise ConnectionError("gone")
    mt5.positions_get = _boom                              # type: ignore[method-assign]
    rep = door.restart_reconcile(mt5, magic=MAGIC, armed=True)
    assert rep["verdict"] == "UNMEASURED"


# ------------------------------------------------------------------ the proxy
def test_the_guarded_module_routes_order_send_and_forwards_everything_else() -> None:
    raw = FakeMT5()
    g = door.guard(raw, caller="gateway")
    assert door.guard(g) is g and door.is_guarded(g)
    assert g.TRADE_ACTION_DEAL == 1 and g.symbol_info_tick("XAUUSD").bid == 2000.0
    g.order_send(_open())
    assert _rows()[-1]["caller"] == "gateway" and len(raw.sent) == 1
    g.some_flag = 3                                       # a test's monkeypatch lands on raw
    assert raw.some_flag == 3
    del g.some_flag
    assert not hasattr(raw, "some_flag")


# ------------------------------------------------------------------ the TradeLocker lanes
class _Venue:
    def __init__(self, ack: bool = True, boom: Exception | None = None) -> None:
        self.ack, self.boom, self.calls = ack, boom, []

    def modify_stop(self, position_id: int, stop: float) -> bool:
        self.calls.append(("modify_stop", position_id, stop))
        if self.boom:
            raise self.boom
        return self.ack

    def cancel(self, order_id: int) -> bool:
        self.calls.append(("cancel", order_id))
        return self.ack

    def positions(self) -> list:
        return [{"id": 1}]


def test_the_guarded_venue_logs_a_raise_and_propagates_it() -> None:
    v = door.guard_venue(_Venue(boom=ConnectionError("disconnected")), caller="e8_gold")
    with pytest.raises(ConnectionError):
        v.modify_stop(1, 1990.0)
    row = _rows()[-1]
    assert row["kind"] == "stop" and row["outcome"] == "exception"


def test_the_guarded_venue_names_an_unacknowledged_write_and_passes_reads_through() -> None:
    raw = _Venue(ack=False)
    v = door.guard_venue(raw, caller="e8_gold")
    assert v.cancel(5) is False and raw.calls == [("cancel", 5)]
    assert _rows()[-1]["outcome"] == "not_acknowledged"
    assert v.positions() == [{"id": 1}]
    assert len(_rows()) == 1, "a read was ledgered as a money action"


def test_e8_gold_intent_journal_failure_is_loud_not_silent(tmp_path, monkeypatch, capsys) -> None:
    from prop import e8_gold
    blocker = tmp_path / "is_a_file"
    blocker.write_text("x")
    monkeypatch.setattr(e8_gold, "INTENTS", blocker / "intents.jsonl")
    monkeypatch.setattr(e8_gold, "LOG", tmp_path / "gold.log")
    assert e8_gold._record({"window": "gold_asia", "side": "buy_stop", "order_id": 42,
                            "status": "SENT"}) is False
    assert "INTENT JOURNAL WRITE FAILED" in capsys.readouterr().out


# ------------------------------------------------------------------ the fence: no bypass
_EXEMPT = {
    # The Fusion ruin rail (Tier-3 class): its flatten must depend on nothing but the terminal,
    # so it is deliberately NOT routed through a module that writes files. Named, not hidden.
    "proposals/fusion_deadman.py",
}


def _order_send_modules() -> list[Path]:
    out = []
    for p in _DESK.rglob("*.py"):
        rel = p.relative_to(_DESK).as_posix()
        if rel.startswith(("tests/", "side_channels/")) or "/_retired/" in f"/{rel}":
            continue
        tree = ast.parse(p.read_text("utf-8"))
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "order_send" for n in ast.walk(tree)):
            out.append(p)
    return out


def test_every_module_that_calls_order_send_binds_mt5_through_the_door() -> None:
    mods = _order_send_modules()
    assert any(p.name == "gateway.py" for p in mods)
    bypass = []
    for p in mods:
        rel = p.relative_to(_DESK).as_posix()
        if rel in _EXEMPT or p.name == "order_door.py":
            continue
        if "_door.guard(" not in p.read_text("utf-8"):
            bypass.append(rel)
    assert not bypass, f"order_send reachable without the order door in: {bypass}"


def test_gateway_binds_the_guarded_module_and_reconciles_before_managing() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    # The raw import stays (other fences read it); the module-level rebinding is what routes
    # every call site, and it must be the LAST module-level binding of `mt5`.
    tree = ast.parse(src)
    binds = [n for n in tree.body if isinstance(n, (ast.Assign, ast.Import))
             and any((isinstance(t, ast.Name) and t.id == "mt5") for t in getattr(n, "targets", []))
             or (isinstance(n, ast.Import) and any((a.asname or a.name) == "mt5" for a in n.names))]
    last = binds[-1]
    assert isinstance(last, ast.Assign), "the raw module is bound as `mt5` after the door"
    assert ast.get_source_segment(src, last.value).startswith("_door.guard(mt5")
    main = src[src.index("\ndef main() -> None:"):]
    assert main.index("_door.restart_reconcile(") < main.index("manage_open_positions(st")


@pytest.mark.parametrize("rel", ["prop/e8_executor.py", "prop/e8_gold.py"])
def test_the_prop_lanes_wrap_their_venue_before_any_write(rel: str) -> None:
    src = (_DESK / rel).read_text("utf-8")
    run = src[src.index("\ndef run("):]
    first_write = min(run.index(w) for w in ("venue.place", "venue.close", "venue.cancel",
                                             "venue.modify_stop", "manage_breakeven(")
                      if w in run)
    assert run.index("order_door.guard_venue(venue") < first_write


def test_the_stop_doors_are_nine_and_all_behind_the_door() -> None:
    """The 25-Sep lane counted nine places that place or move a stop. Five are MT5 sends in the
    gateway (bracket, family entry, scalp entry, trailing SLTP, retarget SLTP) and reach the
    venue only through the guarded `mt5`; four are TradeLocker writes in the prop lanes (entry
    with stop, gold bracket leg with stop, gold ratchet, break-even modify) and reach it only
    through `guard_venue`. If a new one appears this count fails and it must be routed. (The
    restart reconcile's stop restore is a tenth, written inside `order_door` itself and sent
    through `order_door.send`.)"""
    gw = ast.parse((_DESK / "mt5desk" / "gateway.py").read_text("utf-8"))
    mt5_stop_sends = 0
    for fn in (n for n in gw.body if isinstance(n, ast.FunctionDef)):
        for n in ast.walk(fn):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "order_send" and n.args):
                continue
            arg = n.args[0]
            if isinstance(arg, ast.Dict):
                keys = {k.value for k in arg.keys if isinstance(k, ast.Constant)}
                if "sl" in keys:
                    mt5_stop_sends += 1
            elif fn.name == "place_bracket":                 # `order_send(req)`, req carries sl
                mt5_stop_sends += 1
    prop_stop_writes = 0
    for rel in ("prop/e8_executor.py", "prop/e8_gold.py"):
        tree = ast.parse((_DESK / rel).read_text("utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                    and n.func.attr in ("place", "place_stop", "modify_stop") \
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "venue":
                prop_stop_writes += 1
    assert (mt5_stop_sends, prop_stop_writes) == (5, 4)


def test_the_in_doubt_memory_expires() -> None:
    old = {"k": {"at": "2000-01-01T00:00:00+00:00"}}
    assert door._prune(old, datetime.now(tz=UTC)) == {}
