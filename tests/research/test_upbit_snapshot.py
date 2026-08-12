"""R0303 collector: Upbit purges candle history at delisting; these prove the snapshot
survives the purge -- incremental appends, partial-candle exclusion, the delist ledger, and
the refusal paths (an unreachable universe is not an empty universe).

The fake venue emulates the `to=` cursor as EXCLUSIVE (rows strictly older), newest-first,
200/page -- the shape the real walker sees.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from libs.research import upbit_data as ud
from scripts import run_upbit_snapshot as snap


def _mkt(name: str, warning: bool = False) -> dict[str, Any]:
    return {"market": name, "korean_name": "x", "english_name": "x",
            "market_event": {"warning": warning, "caution": {}}}


def _candle(mkt: str, key: str) -> dict[str, Any]:
    return {"market": mkt, "candle_date_time_utc": key, "trade_price": 1.0,
            "candle_acc_trade_volume": 2.0}


class FakeVenue:
    """History per (path, market), newest-first pages, exclusive `to` cursor."""

    def __init__(self, history: dict[tuple[str, str], list[str]],
                 broken: set[str] = frozenset()):
        self.history = {k: sorted(v, reverse=True) for k, v in history.items()}
        self.broken = set(broken)
        self.calls = 0

    def fetch(self, path: str, market: str, count: int, to: str,
              timeout: int) -> list[dict[str, Any]]:
        self.calls += 1
        if market in self.broken:
            raise OSError(f"venue 500 for {market}")
        keys = self.history.get((path, market), [])
        if to:
            keys = [k for k in keys if k < to]
        return [_candle(market, k) for k in keys[:count]]


def _run(monkeypatch, tmp_path: Path, markets, venue: FakeVenue,
         argv: list[str] | None = None) -> int:
    monkeypatch.setattr(snap, "guard", lambda **kw: None)
    monkeypatch.setattr(ud, "fetch_markets", lambda timeout=35: markets)
    monkeypatch.setattr(ud, "_fetch_raw", venue.fetch)
    monkeypatch.setattr(ud, "_time",
                        type("T", (), {"sleep": staticmethod(lambda s: None)}))
    return snap.main(["--root", str(tmp_path), *(argv or [])])


def _rows(p: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in p.read_text("utf-8").splitlines()]


def test_backfill_then_incremental_appends_only_new(monkeypatch, tmp_path):
    hist = ["2026-08-01T00:00:00", "2026-08-02T00:00:00", "2026-08-03T00:00:00"]
    venue = FakeVenue({("days", "KRW-AAA"): list(hist)})
    rc = _run(monkeypatch, tmp_path, [_mkt("KRW-AAA")], venue, ["--no-minute"])
    assert rc == 0
    rows = _rows(tmp_path / "daily/KRW-AAA.jsonl")
    assert [ud.candle_key(r) for r in rows] == hist          # ascending, complete
    assert all("_recv" in r for r in rows)                   # our clock beside the venue's

    # A new day arrives; the second run appends ONLY it.
    venue.history[("days", "KRW-AAA")].insert(0, "2026-08-04T00:00:00")
    rc = _run(monkeypatch, tmp_path, [_mkt("KRW-AAA")], venue, ["--no-minute"])
    assert rc == 0
    rows = _rows(tmp_path / "daily/KRW-AAA.jsonl")
    assert [ud.candle_key(r) for r in rows] == [*hist, "2026-08-04T00:00:00"]
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert man["markets"]["KRW-AAA"]["rows"] == 4
    assert man["markets"]["KRW-AAA"]["last"] == "2026-08-04T00:00:00"


def test_in_progress_candles_are_never_stored(monkeypatch, tmp_path):
    from datetime import UTC, datetime
    today = datetime.now(tz=UTC).strftime("%Y-%m-%dT00:00:00")
    venue = FakeVenue({("days", "KRW-AAA"): ["2026-08-01T00:00:00", today]})
    assert _run(monkeypatch, tmp_path, [_mkt("KRW-AAA")], venue, ["--no-minute"]) == 0
    keys = [ud.candle_key(r) for r in _rows(tmp_path / "daily/KRW-AAA.jsonl")]
    assert keys == ["2026-08-01T00:00:00"]                   # today's partial row excluded


def test_delist_is_recorded_and_files_preserved(monkeypatch, tmp_path):
    venue = FakeVenue({("days", "KRW-AAA"): ["2026-08-01T00:00:00"],
                       ("days", "KRW-BBB"): ["2026-08-01T00:00:00"]})
    both = [_mkt("KRW-AAA"), _mkt("KRW-BBB")]
    assert _run(monkeypatch, tmp_path, both, venue, ["--no-minute"]) == 0

    # BBB vanishes from the venue's own list -- the delist event.
    assert _run(monkeypatch, tmp_path, [_mkt("KRW-AAA")], venue, ["--no-minute"]) == 0
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert "KRW-BBB" in man["delisted"]
    assert man["delisted"]["KRW-BBB"]["rows"] == 1
    assert (tmp_path / "daily/KRW-BBB.jsonl").exists()       # preserved forever


def test_refuses_when_market_list_unreachable(monkeypatch, tmp_path):
    monkeypatch.setattr(snap, "guard", lambda **kw: None)

    def boom(timeout=35):
        raise OSError("dns down")
    monkeypatch.setattr(ud, "fetch_markets", boom)
    assert snap.main(["--root", str(tmp_path)]) == 2
    assert not (tmp_path / "manifest.json").exists()         # nothing written on refusal


def test_failed_market_is_recorded_not_skipped(monkeypatch, tmp_path):
    venue = FakeVenue({("days", "KRW-AAA"): ["2026-08-01T00:00:00"],
                       ("days", "KRW-BBB"): ["2026-08-01T00:00:00"]},
                      broken={"KRW-BBB"})
    rc = _run(monkeypatch, tmp_path, [_mkt("KRW-AAA"), _mkt("KRW-BBB")], venue,
              ["--no-minute"])
    assert rc == 1                                           # 1/2 failed > 10% tail
    man = json.loads((tmp_path / "manifest.json").read_text())
    assert any(f.startswith("KRW-BBB:days:") for f in man["last_run_summary"]["failures"])
    assert (tmp_path / "daily/KRW-AAA.jsonl").exists()       # the healthy market still landed


def test_flagged_market_gets_minute_rows_in_trailing_window_only(monkeypatch, tmp_path):
    from datetime import UTC, datetime, timedelta
    now = datetime.now(tz=UTC)
    fresh = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:00")
    stale = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:00")
    day = (now - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00")
    venue = FakeVenue({("days", "KRW-ZZZ"): [day],
                       ("minutes/1", "KRW-ZZZ"): [stale, fresh]})
    assert _run(monkeypatch, tmp_path, [_mkt("KRW-ZZZ", warning=True)], venue) == 0
    keys = [ud.candle_key(r) for r in _rows(tmp_path / "minute/KRW-ZZZ.jsonl")]
    assert keys == [fresh]                                   # 90d-old row is outside the window


def test_walker_orders_ascending_and_reports_partial(monkeypatch):
    venue = FakeVenue({("days", "X"): [f"2026-07-{d:02d}T00:00:00" for d in range(1, 8)]})
    monkeypatch.setattr(ud, "_fetch_raw", venue.fetch)
    monkeypatch.setattr(ud, "_time",
                        type("T", (), {"sleep": staticmethod(lambda s: None)}))
    rows, complete = ud.walk_candles_raw("X", path="days",
                                         stop_before_key="2026-07-03T00:00:00")
    assert complete
    assert [ud.candle_key(r) for r in rows] == [f"2026-07-{d:02d}T00:00:00"
                                                for d in range(4, 8)]

    def broken(path, market, count, to, timeout):
        raise OSError("mid-walk 500")
    monkeypatch.setattr(ud, "_fetch_raw", broken)
    rows, complete = ud.walk_candles_raw("X", path="days")
    assert rows == [] and not complete                       # loud partial, never silent
