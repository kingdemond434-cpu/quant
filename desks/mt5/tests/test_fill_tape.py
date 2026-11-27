"""ROOT R5 (2026-11-27): every executor writes one fill-tape row at the fill; PROP_SLIP.json
is derived from the tape, never a default."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import fill_tape as ft  # noqa: E402
from mt5desk import order_door as door  # noqa: E402
from prop import e8_fills  # noqa: E402

NOW = datetime(2026, 11, 27, 5, 6, 33, tzinfo=UTC)


def test_slip_is_positive_when_worse_for_the_trader() -> None:
    assert ft.slip("buy", 100.0, 100.1) == (0.001, 0.1)
    assert ft.slip("sell", 100.0, 99.9)[0] == 0.001
    assert ft.slip("buy", 100.0, 99.9)[0] == -0.001
    assert ft.slip("buy", None, 100.0) == (None, None)
    assert ft.slip("hold", 100.0, 100.0) == (None, None)


def test_a_row_names_what_it_did_not_read_and_never_defaults_to_zero() -> None:
    r = ft.row(book="e8", venue="tradelocker", lane="e8_gold", symbol="xauusd", side="buy",
               intended=None, fill=3637.95, deal=7, at=NOW)
    assert r["slip_frac"] is None and r["spread_px"] is None and len(r["unmeasured"]) == 2
    assert r["symbol"] == "XAUUSD" and r["deal"] == "7"


def test_record_never_raises_and_refuses_an_account_field(tmp_path) -> None:
    assert ft.record({"x": 1, "login": 5}, path=tmp_path / "t.jsonl") is False
    assert ft.record({"x": 1}, path=tmp_path / "no" / "t.jsonl") is True
    assert ft.record({"x": 1}, path=Path("/proc/forbidden/t.jsonl")) is False


def test_the_summary_is_per_book_and_symbol_and_unmeasured_when_unpriced(tmp_path) -> None:
    t = tmp_path / "fill_tape.jsonl"
    for i, fill in enumerate((100.1, 100.2, 100.0)):
        ft.record(ft.row(book="ftmo", venue="mt5", lane="ftmo_executor", symbol="EURUSD",
                         side="buy", intended=100.0, fill=fill, bid=99.99, ask=100.0,
                         deal=i, at=NOW), path=t)
    ft.record(ft.row(book="ftmo", venue="mt5", lane="ftmo_executor", symbol="EURUSD",
                     side="buy", intended=100.0, fill=100.1, deal=0, at=NOW), path=t)  # dup
    ft.record(ft.row(book="e8", venue="tradelocker", lane="e8_gold", symbol="XAUUSD",
                     side="buy", intended=None, fill=1.0, deal=9, at=NOW), path=t)
    doc = ft.publish(tape=t, out=tmp_path / "PROP_SLIP.json", now=NOW)
    eu = doc["books"]["ftmo"]["EURUSD"]
    assert eu["n_rows"] == 3 and eu["status"] == "MEASURED"
    assert eu["slip_px_median"] == 0.1 and eu["spread_px_median"] == 0.01
    assert doc["books"]["e8"]["XAUUSD"]["status"] == "UNMEASURED"
    assert json.loads((tmp_path / "PROP_SLIP.json").read_text("utf-8")) == doc


class _MT5:
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1

    def __init__(self, price: float, retcode: int = door.RETCODE_DONE) -> None:
        self.price, self.retcode = price, retcode

    def order_check(self, req):
        return SimpleNamespace(retcode=0, comment="")

    def symbol_info_tick(self, sym):
        return SimpleNamespace(bid=1.0999, ask=1.1001)

    def order_send(self, req):
        return SimpleNamespace(retcode=self.retcode, price=self.price, volume=req["volume"],
                               deal=4242, order=1, comment="")


def _req(**kw):
    return {"action": 1, "symbol": "EURUSD", "type": 0, "volume": 0.1, "price": 1.1001,
            "sl": 1.09, "magic": 1, "comment": "t", **kw}


def test_the_door_tapes_a_done_market_deal_with_its_quote(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    door.send(_MT5(1.1003), _req(), caller="ftmo_executor")
    (r,) = ft.read(tmp_path / "fill_tape.jsonl")
    assert r["book"] == "ftmo" and r["side"] == "buy" and r["kind"] == "entry"
    assert r["intended"] == 1.1001 and r["fill"] == 1.1003 and r["deal"] == "4242"
    assert r["spread_px"] == 0.0002 and r["slip_px"] > 0


def test_the_door_tapes_nothing_for_a_rejected_or_pending_send(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    door.send(_MT5(1.1003, retcode=10006), _req(), caller="gateway")
    door.send(_MT5(1.1003, retcode=door.RETCODE_PLACED), _req(action=5), caller="gateway")
    assert ft.read(tmp_path / "fill_tape.jsonl") == []


def test_a_close_is_taped_as_an_exit_on_its_book(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MT5_ORDER_DOOR_DIR", str(tmp_path))
    door.send(_MT5(1.0990), _req(type=1, position=77, price=1.0999), caller="gateway")
    (r,) = ft.read(tmp_path / "fill_tape.jsonl")
    assert r["book"] == "fusion" and r["kind"] == "exit" and r["side"] == "sell"


class _Venue:
    def __init__(self, positions):
        self._positions, self._by_key = positions, {"XAUUSD": 6102}

    def positions(self):
        return self._positions

    def account(self):
        return {"balance": 102868.89}


def test_an_e8_position_seen_first_is_one_entry_fill_against_its_sent_leg(tmp_path) -> None:
    intents = tmp_path / "intents.jsonl"
    intents.write_text(json.dumps({"status": "SENT", "side": "buy_stop", "at": NOW.isoformat(),
                                   "price": 3637.92, "sl": 3557.54, "lot": 0.07}) + "\n",
                       encoding="utf-8")
    pos = [{"id": 11, "side": "buy", "qty": 0.07, "avgPrice": 3638.20,
            "tradableInstrumentId": 6102}]
    kw = {"state": tmp_path / "st.json", "ledger": tmp_path / "l.jsonl", "intents": intents}
    out = e8_fills.observe(_Venue(pos), now=NOW, **kw)
    assert out["taped"] == 1
    assert e8_fills.observe(_Venue(pos), now=NOW, **kw)["taped"] == 0   # seen before
    (r,) = ft.read(tmp_path / "fill_tape.jsonl")
    assert r["book"] == "e8" and r["intended"] == 3637.92 and r["fill"] == 3638.2
    assert r["slip_px"] == round(3638.20 - 3637.92, 6)
    slip = json.loads((tmp_path / "PROP_SLIP.json").read_text("utf-8"))
    assert slip["books"]["e8"]["XAUUSD"]["n_priced"] == 1
