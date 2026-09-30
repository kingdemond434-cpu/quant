from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from research import dukascopy_backfill as db


def test_transient_failure_does_not_advance_cursor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(db, "SYMBOLS", ("XAUUSD",))
    monkeypatch.setattr(db, "fetch_day", lambda *a, **k: {
        "symbol": "XAUUSD", "day": "2026-09-26", "status": "RETRY", "ticks": 0,
    })
    state = tmp_path / "state.json"
    report = db.run(root=tmp_path / "ticks", state_path=state,
                    report_path=tmp_path / "report.json", symbol_days=1,
                    now=datetime(2026, 9, 27, 12, tzinfo=UTC))
    assert report["retry"] == 1
    assert json.loads(state.read_text())["next_date"]["XAUUSD"] == "2026-09-26"


def test_complete_day_is_atomic_and_advances(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(db, "SYMBOLS", ("XAUUSD",))

    def fake_hour(symbol, when, pause=0.0):
        ms = int(when.timestamp() * 1000)
        return [(ms, 3300.0, 3300.2, 1.0, 1.0)], "ok"

    monkeypatch.setattr(db, "fetch_hour", fake_hour)
    state = tmp_path / "state.json"
    report = db.run(root=tmp_path / "ticks", state_path=state,
                    report_path=tmp_path / "report.json", symbol_days=1,
                    now=datetime(2026, 9, 27, 12, tzinfo=UTC))
    target = db._day_path(tmp_path / "ticks", "XAUUSD", date(2026, 9, 26))
    assert report["written"] == 1
    assert target.exists() and not target.with_suffix(target.suffix + ".partial").exists()
    assert len(pd.read_parquet(target)) == 24
    assert json.loads(state.read_text())["next_date"]["XAUUSD"] == "2026-09-25"


def test_existing_partition_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    target = db._day_path(tmp_path, "XAUUSD", date(2026, 9, 26))
    target.parent.mkdir(parents=True)
    target.write_bytes(b"already-complete")
    monkeypatch.setattr(db, "fetch_hour", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("network must not be touched for a completed partition")))
    result = db.fetch_day("XAUUSD", date(2026, 9, 26), tmp_path)
    assert result["status"] == "EXISTS"
