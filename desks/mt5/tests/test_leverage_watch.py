"""K3 leverage watch: read-only snapshots from a fake terminal, change detection, feasibility of
every sized order at today's margin and at half leverage, and the cut-prone window."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import leverage_watch as lw  # noqa: E402


class FakeMT5:
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1

    def __init__(self, leverage: int = 100, gold_margin_mult: float = 1.0) -> None:
        self.leverage = leverage
        self.gm = gold_margin_mult
        self.sent: list = []

    def account_info(self):
        return SimpleNamespace(server="FTMO-Server2", company="FTMO Global Markets Ltd",
                               currency="USD", leverage=self.leverage, margin_mode=2,
                               margin_so_call=100.0, margin_so_so=50.0, margin_so_mode=0,
                               equity=100_000.0, margin=0.0, margin_free=100_000.0, login=123)

    def symbol_info(self, sym):
        if sym not in ("XAUUSD", "EURUSD"):
            return None
        return SimpleNamespace(trade_contract_size=100.0 if sym == "XAUUSD" else 100_000.0,
                               margin_initial=0.0, margin_maintenance=0.0, margin_hedged=0.0,
                               volume_min=0.01, visible=True)

    def symbol_info_tick(self, sym):
        px = 4000.0 if sym == "XAUUSD" else 1.10
        return SimpleNamespace(bid=px - 0.1 * (sym == "XAUUSD"), ask=px)

    def order_calc_margin(self, otype, sym, lot, price):
        cs = 100.0 if sym == "XAUUSD" else 100_000.0
        mult = self.gm if sym == "XAUUSD" else 1.0
        return cs * lot * price / self.leverage * mult

    def order_send(self, *a, **k):        # pragma: no cover - must never be called
        self.sent.append(a)
        raise AssertionError("leverage watch must never send")


def _intents(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_snapshot_is_read_only_and_names_no_login(tmp_path: Path) -> None:
    mt5 = FakeMT5()
    snap = lw.mt5_snapshot(mt5, ["XAUUSD", "EURUSD", "NOPE"])
    assert snap is not None and snap["venue"] == "ftmo" and snap["leverage"] == 100
    assert set(snap["symbols"]) == {"XAUUSD", "EURUSD"}
    assert snap["symbols"]["XAUUSD"]["effective_leverage"] == pytest.approx(100.0)
    assert "login" not in json.dumps(snap) and "123" not in json.dumps(snap["symbols"])
    assert mt5.sent == []


def test_record_dedupes_unchanged_and_writes_on_change(tmp_path: Path) -> None:
    h = tmp_path / "h.jsonl"
    assert lw.record(lw.mt5_snapshot(FakeMT5(), ["XAUUSD"]), h)
    assert not lw.record(lw.mt5_snapshot(FakeMT5(), ["XAUUSD"]), h)          # unchanged
    assert lw.record(lw.mt5_snapshot(FakeMT5(gold_margin_mult=2.0), ["XAUUSD"]), h)
    assert len(h.read_text().splitlines()) == 2


def test_record_mt5_never_raises() -> None:
    class Broken:
        def account_info(self):
            raise RuntimeError("terminal gone")
    assert "failed" in lw.record_mt5(Broken())


def _history(tmp_path: Path, snaps: list[tuple[datetime, FakeMT5]]) -> Path:
    h = tmp_path / "h.jsonl"
    for at, m in snaps:
        s = lw.mt5_snapshot(m, ["XAUUSD", "EURUSD"])
        assert s is not None
        s["at"] = at.isoformat()
        lw.record(s, h)
    return h


def test_assess_detects_symbol_cut_and_goes_red(tmp_path: Path) -> None:
    now = datetime(2026, 11, 11, 10, tzinfo=UTC)         # a Wednesday
    h = _history(tmp_path, [(now - timedelta(hours=30), FakeMT5()),
                            (now - timedelta(hours=2), FakeMT5(gold_margin_mult=5.0))])
    files = {"main": tmp_path / "none.jsonl", "ftmo": tmp_path / "f.jsonl",
             "e8": tmp_path / "e.jsonl"}
    _intents(files["ftmo"], [])
    doc = lw.assess(now, h, files, tmp_path / "cal")
    v = doc["venues"]["ftmo"]
    assert any(c["scope"] == "XAUUSD" and c["kind"] == "CUT" for c in v["changes_7d"])
    assert v["status"] == "RED" and doc["status"] == "RED"


def test_feasibility_today_and_at_half_leverage_in_weekend_window(tmp_path: Path) -> None:
    friday = datetime(2026, 11, 13, 15, tzinfo=UTC)
    h = _history(tmp_path, [(friday - timedelta(minutes=5), FakeMT5(leverage=30))])
    files = {"main": tmp_path / "none.jsonl", "ftmo": tmp_path / "f.jsonl",
             "e8": tmp_path / "e.jsonl"}
    # 2.2 lots gold at 1:30 = 29,333 margin each side; capacity = 100k x 0.5 = 50k:
    # fits today alone, but not at half leverage (58,667)
    _intents(files["ftmo"], [{"sleeve": "g", "symbol": "XAUUSD", "side": "buy", "lot": 2.2,
                              "time": (friday - timedelta(days=1)).isoformat()}])
    doc = lw.assess(friday, h, files, tmp_path / "cal")
    v = doc["venues"]["ftmo"]
    assert v["feasibility"]["book_fits"] is True
    assert v["stress_half_leverage"]["book_fits"] is False
    assert doc["cut_prone_window"]["now"] is True
    assert v["status"] == "AMBER"


def test_infeasible_sized_order_is_red(tmp_path: Path) -> None:
    now = datetime(2026, 11, 11, 10, tzinfo=UTC)
    h = _history(tmp_path, [(now - timedelta(minutes=5), FakeMT5(leverage=10))])
    files = {"main": tmp_path / "none.jsonl", "ftmo": tmp_path / "f.jsonl",
             "e8": tmp_path / "e.jsonl"}
    _intents(files["ftmo"], [{"sleeve": "g", "symbol": "XAUUSD", "side": "buy", "lot": 2.0,
                              "time": (now - timedelta(days=2)).isoformat()}])
    v = lw.assess(now, h, files, tmp_path / "cal")["venues"]["ftmo"]
    assert v["status"] == "RED" and v["feasibility"]["orders_infeasible_alone"]


def test_stale_or_absent_history_is_unmeasured(tmp_path: Path) -> None:
    now = datetime(2026, 11, 11, 10, tzinfo=UTC)
    assert lw.assess(now, tmp_path / "none.jsonl", lw.INTENT_FILES,
                     tmp_path / "cal")["status"] == "UNMEASURED"
    h = _history(tmp_path, [(now - timedelta(hours=9), FakeMT5())])
    doc = lw.assess(now, h, {"main": tmp_path / "x", "ftmo": tmp_path / "y",
                             "e8": tmp_path / "z"}, tmp_path / "cal")
    assert doc["venues"]["ftmo"]["status"] == "UNMEASURED"


def test_calendar_event_opens_the_window(tmp_path: Path) -> None:
    now = datetime(2026, 11, 11, 10, tzinfo=UTC)
    cal = tmp_path / "cal"
    cal.mkdir()
    (cal / "fomc.json").write_text(json.dumps(
        {"events": [{"time": (now + timedelta(hours=6)).isoformat()}]}))
    ok, why = lw.in_event_window(now, cal)
    assert ok and "fomc" in why
    assert lw.in_event_window(now, tmp_path / "none")[0] is False


def test_price_move_alone_is_not_a_leverage_change(tmp_path: Path) -> None:
    a = lw.mt5_snapshot(FakeMT5(), ["XAUUSD"])
    b = json.loads(json.dumps(a))
    b["symbols"]["XAUUSD"]["price"] *= 1.3
    b["symbols"]["XAUUSD"]["margin_per_lot_buy"] *= 1.3
    b["at"] = (datetime.fromisoformat(a["at"]) + timedelta(hours=1)).isoformat()
    assert lw.changes([a, b], datetime.fromisoformat(b["at"])) == []


def test_history_is_bounded_and_keeps_each_venues_latest(tmp_path: Path, monkeypatch) -> None:
    h = tmp_path / "h.jsonl"
    old = datetime.now(UTC) - timedelta(days=200)
    rows = [{"venue": "fusion", "at": old.isoformat(), "fingerprint": "a"}]
    rows += [{"venue": "ftmo", "at": (old + timedelta(minutes=i)).isoformat(),
              "fingerprint": str(i)} for i in range(30)]
    h.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(lw, "MAX_ROWS", 10)
    lw._trim(h, keep_days=45, max_rows=10)
    kept = [json.loads(x) for x in h.read_text().splitlines()]
    assert {r["venue"] for r in kept} == {"fusion", "ftmo"} and len(kept) == 2
