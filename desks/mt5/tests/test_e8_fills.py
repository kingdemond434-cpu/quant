"""THE E8 SIDE OF THE PROP FILLS LEDGER (prop/e8_fills.py): closed E8 gold positions, book "e8".

Fake TradeLocker order-history rows and fake ids only; every ledger path is under tmp_path.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import e8_fills as ef  # noqa: E402
from prop import ftmo_follower as ff  # noqa: E402

IID = 4711
NOW = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
SERVER_TIME = "2026-10-21T12:00:00+00:00"           # the terminal tick: UTC+3 server wall clock
SENT_AT = "2026-10-21T04:00:20+00:00"               # 07:00 server: the asia signal pass
MS = int(datetime(2026, 10, 21, 4, 30, tzinfo=UTC).timestamp() * 1000)
KEY = "k" * 64


def _hist(*, pid: int = 9, exit_px: float = 4319.8, exit_type: str = "stop",
          exit_qty: float = 0.5) -> list[dict]:
    return [
        {"id": 101, "status": "Filled", "positionId": pid, "side": "buy", "type": "stop",
         "avgPrice": 4340.4, "filledQty": 0.5, "qty": 0.5, "tradableInstrumentId": IID,
         "createdDate": MS - 1_800_000, "lastModified": MS},
        {"id": 102, "status": "Cancelled", "positionId": None, "side": "sell", "type": "stop",
         "avgPrice": None, "filledQty": 0, "qty": 0.5, "tradableInstrumentId": IID,
         "createdDate": MS - 1_800_000, "lastModified": MS},
        {"id": 103, "status": "Filled", "positionId": pid, "side": "sell", "type": exit_type,
         "avgPrice": exit_px, "filledQty": exit_qty, "qty": exit_qty,
         "tradableInstrumentId": IID, "createdDate": MS, "lastModified": MS + 600_000},
        # somebody else's round trip on the account: not this lane's entry order, never written
        {"id": 900, "status": "Filled", "positionId": 55, "side": "buy", "type": "market",
         "avgPrice": 4300.0, "filledQty": 1.0, "tradableInstrumentId": IID, "lastModified": MS},
        {"id": 901, "status": "Filled", "positionId": 55, "side": "sell", "type": "market",
         "avgPrice": 4310.0, "filledQty": 1.0, "tradableInstrumentId": IID, "lastModified": MS},
    ]


OWN = {101: {"window": "asia", "side": "buy_stop", "price": 4340.0, "sl": 4320.0,
             "tp": 4380.0, "lot": 0.5},
       102: {"window": "asia", "side": "sell_stop", "price": 4300.0, "sl": 4320.0,
             "tp": 4260.0, "lot": 0.5}}
JOURNAL = [{"at": SENT_AT, "window": "asia", "side": "buy_stop", "status": "SENT",
            "order_id": 101}]


class _Venue:
    def __init__(self, details: object = None) -> None:
        self._d = {"contractSize": 100.0} if details is None else details

    def details(self, symbol: str) -> dict:
        if isinstance(self._d, Exception):
            raise self._d
        return self._d


def _record(path: Path, hist: list[dict] | None = None, *, open_ids: set[int] | None = None,
            venue: object = None, **kw: object) -> dict:
    args = {"history_ok": True, "positions_ok": True, "instrument_id": IID,
            "account_key": KEY, "server_time": SERVER_TIME, "now": NOW, "path": path}
    args.update(kw)
    return ef.record_fills(venue or _Venue(), _hist() if hist is None else hist, OWN, JOURNAL,
                           open_ids or set(), **args)


def _rows(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()] \
        if path.exists() else []


def test_a_closed_e8_position_is_written_once_in_prop_fills_v1(tmp_path) -> None:
    path = tmp_path / "live_ledger_prop.jsonl"
    assert _record(path) == {"written": 1, "closed_seen": 1}
    assert _record(path)["written"] == 0                       # deduped by e8:<position>
    (row,) = _rows(path)
    assert row["schema"] == ff.PROP_SCHEMA == "prop-fills-v1"
    assert (row["book"], row["venue"], row["position_id"]) == ("e8", "tradelocker", 9)
    assert (row["entry_side"], row["side"], row["entry_price"], row["fill_price"]) == (
        0, 1, 4340.4, 4319.8)
    assert (row["sl"], row["tp"], row["intended_entry"], row["volume"]) == (
        4320.0, 4380.0, 4340.0, 0.5)
    assert row["exit_reason"] == "stop" and row["closed_by"] == "venue"
    assert row["r_multiple"] == pytest.approx(-20.6 / 20.4, abs=1e-4)
    assert row["pl_quote"] == pytest.approx(-20.6 * 0.5 * 100.0)
    assert row["risk_quote"] == pytest.approx(20.4 * 0.5 * 100.0)
    assert row["account_key"] == KEY and row["entry_order"] == 101 and row["close_order"] == 103


def test_the_episode_fields_name_the_signal_hour_direction_and_sleeve(tmp_path) -> None:
    path = tmp_path / "l.jsonl"
    _record(path)
    (row,) = _rows(path)
    # asia's signal hour is 07:00 on the UTC+3 server clock = 04:00 UTC
    assert row["signal_hour_utc"] == "2026-10-21T04:00:00+00:00"
    assert row["direction"] == 1 and row["sleeve"] == "gold_asia" and row["window"] == "asia"
    short = _hist()
    short[0]["side"], short[2]["side"] = "sell", "buy"
    path2 = tmp_path / "s.jsonl"
    _record(path2, short)
    assert _rows(path2)[0]["direction"] == -1


def test_ftmo_rows_carry_the_same_episode_key_as_e8s() -> None:
    """FTMO's copy of the same asia signal: its entry deal sits later on the same server date,
    so the derived signal hour is E8's, and the Auditor can collapse the two rows."""
    tick = int(datetime(2026, 10, 21, 8, 30, tzinfo=UTC).timestamp())   # server wall clock
    deals = (SimpleNamespace(ticket=1, order=7, position_id=7, symbol="XAUUSD", magic=ff.MAGIC,
                             entry=0, type=0, volume=0.45, price=4340.4, time=tick, profit=0.0,
                             commission=-3.5, swap=0.0, fee=0.0, reason=3),
             SimpleNamespace(ticket=2, order=8, position_id=7, symbol="XAUUSD", magic=ff.MAGIC,
                             entry=1, type=1, volume=0.45, price=4319.8, time=tick + 600,
                             profit=-927.0, commission=-3.5, swap=0.0, fee=0.0, reason=4))
    orders = [SimpleNamespace(ticket=7, sl=4320.0, tp=4380.0, price_open=4340.0)]
    (ft,) = ff.compose_fills(deals, orders, set(), account_key=None, contract=100.0,
                             recorded_at="x", server_offset_h=3)
    assert (ft["direction"], ft["sleeve"], ft["signal_hour_utc"]) == (
        1, "gold_asia", "2026-10-21T04:00:00+00:00")
    (unmeasured,) = ff.compose_fills(deals, orders, set(), account_key=None, contract=100.0,
                                     recorded_at="x")
    assert unmeasured["signal_hour_utc"] is None
    assert unmeasured["signal_hour_basis"].startswith("UNMEASURED")


def test_an_open_unpriced_or_partly_closed_trade_is_never_written(tmp_path) -> None:
    path = tmp_path / "l.jsonl"
    assert _record(path, open_ids={9})["written"] == 0               # still open
    assert _record(path, _hist(exit_px=None))["written"] == 0        # exit unpriced
    assert _record(path, _hist(exit_qty=0.2))["written"] == 0        # exits do not cover it
    assert _record(path, positions_ok=False)["written"] == 0
    assert _record(path, history_ok=False)["written"] == 0
    assert _rows(path) == []


def test_unknown_fees_and_contract_are_null_with_a_status_never_zero(tmp_path) -> None:
    path = tmp_path / "l.jsonl"
    _record(path, venue=_Venue(details=RuntimeError("down")), server_time=None)
    (row,) = _rows(path)
    assert (row["commission"], row["swap"], row["fees"], row["pl_net_quote"]) == (
        None, None, None, None)
    assert row["fees_status"].startswith("UNMEASURED") and row["fees_measured"] == []
    assert row["pl_quote"] is None and row["pl_basis"].startswith("UNMEASURED")
    assert row["signal_hour_utc"] is None and row["r_multiple"] is not None


def test_dedupe_is_per_book_across_both_writers(tmp_path) -> None:
    path = tmp_path / "l.jsonl"
    ff.append_fills([{"schema": "prop-fills-v1", "book": "ftmo", "position_id": 9}], path)
    assert _record(path)["written"] == 1                    # ftmo:9 does not hide e8:9
    assert ff.append_fills([{"book": "ftmo", "position_id": 9}], path) == 0
    assert ef.append_fills([{"book": "e8", "position_id": 9}], path) == 0
    assert ef.append_fills([{"book": "e8", "position_id": 10}] * 2, path) == 1   # in-batch
    assert sorted(f"{r['book']}:{r['position_id']}" for r in _rows(path)) == [
        "e8:10", "e8:9", "ftmo:9"]
    with pytest.raises(ValueError, match="book 'e8' only"):
        ef.append_fills([{"book": "ftmo", "position_id": 11}], path)


@pytest.mark.parametrize("field", ff.PROP_BANNED)
def test_a_login_shaped_field_is_refused(tmp_path, field: str) -> None:
    path = tmp_path / "l.jsonl"
    with pytest.raises(ValueError, match=field):
        ef.append_fills([{"book": "e8", "position_id": 1, field: "x"}], path)
    assert not path.exists()
    (row,) = ef.compose_fills(_hist(), OWN, JOURNAL, set(), instrument_id=IID, contract=100.0,
                              account_key=KEY, server_offset=3, venue_clock_skew_ms=None,
                              recorded_at="x")
    assert not any(k in row for k in ff.PROP_BANNED)


def test_record_fills_never_raises(tmp_path, monkeypatch) -> None:
    def boom(rows: object, path: object = None) -> int:
        raise OSError("disk full")
    monkeypatch.setattr(ef, "append_fills", boom)
    out = _record(tmp_path / "l.jsonl")
    assert out["written"] == 0 and "OSError" in out["why"]
    junk = [{"id": "x", "status": "Filled", "positionId": object()}, None]
    out = ef.record_fills(_Venue(), junk, OWN, [None], {1}, history_ok=True,  # type: ignore[list-item]
                          positions_ok=True, instrument_id=IID, account_key=None,
                          server_time=object(), now=NOW, path=tmp_path / "j.jsonl")
    assert out["written"] == 0


_WRITER = """
import sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from pathlib import Path
from prop import e8_fills as ef, ftmo_follower as ff
book, base = sys.argv[4], int(sys.argv[5])
path = Path(sys.argv[3])
write = ff.append_fills if book == "ftmo" else ef.append_fills
for i in range(150):
    write([{"schema": "prop-fills-v1", "book": book, "position_id": base + i,
            "pad": "x" * 900}], path)
"""


def test_the_e8_and_ftmo_writers_interleave_without_tearing_a_line(tmp_path) -> None:
    script = tmp_path / "writer.py"
    script.write_text(_WRITER, "utf-8")
    path = tmp_path / "shared.jsonl"
    procs = [subprocess.Popen([sys.executable, str(script), str(_DESK), str(_DESK.parent.parent),
                               str(path), book, str(base)])
             for book, base in (("ftmo", 1000), ("e8", 5000))]
    assert all(p.wait(timeout=120) == 0 for p in procs)
    rows = [json.loads(ln) for ln in path.read_text("utf-8").splitlines()]
    assert len(rows) == 300
    assert {f"{r['book']}:{r['position_id']}" for r in rows} == (
        {f"ftmo:{1000 + i}" for i in range(150)} | {f"e8:{5000 + i}" for i in range(150)})
