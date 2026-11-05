"""The million-row intake must not allocate a second JSON-sized string."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
from research import merge_hypotheses as merge  # noqa: E402


def test_streamed_docket_round_trips_without_dumps(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "external_survivors.json"
    rows = [{"symbol": "USDJPY", "params": {"rr": 1.5}},
            {"symbol": "EURUSD", "params": {"rr": 2.0}}]

    original_dumps = json.dumps

    def one_row_dumps(value, **kwargs):
        assert isinstance(value, dict), "never serialize the entire docket at once"
        return original_dumps(value, **kwargs)

    monkeypatch.setattr(merge.json, "dumps", one_row_dumps)
    merge._write_docket_atomically(target, rows)
    actual = json.loads(target.read_text("utf-8"))
    # The canonical publisher groups symbols for streaming judge consumption.
    # Every row and parameter must survive even when physical row order changes.
    assert sorted(actual, key=lambda r: r["symbol"]) == sorted(rows, key=lambda r: r["symbol"])
    assert [r["symbol"] for r in actual] == ["EURUSD", "USDJPY"]
    assert list(tmp_path.glob("*.tmp")) == []


def test_failed_stream_keeps_prior_docket(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "external_survivors.json"
    target.write_text('[{"symbol":"old"}]', encoding="utf-8")

    def interrupted(*_args, **_kwargs):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(merge.json, "dumps", interrupted)
    with pytest.raises(OSError, match="simulated disk failure"):
        merge._write_docket_atomically(target, [{"symbol": "new"}])
    assert json.loads(target.read_text("utf-8")) == [{"symbol": "old"}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_the_rename_waits_out_a_reader_holding_the_docket(tmp_path: Path, monkeypatch) -> None:
    """Windows refuses os.replace onto an open file (WinError 5): 28 failures on the box froze the
    docket for 54 h. A reader that lets go inside the budget no longer costs the write."""
    target = tmp_path / "external_survivors.json"
    target.write_text('[{"symbol":"old"}]', encoding="utf-8")
    real = merge.os.replace
    calls = {"n": 0}

    def busy_twice(src, dst):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError(5, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(merge.os, "replace", busy_twice)
    monkeypatch.setattr(merge.time, "sleep", lambda s: None)
    merge._write_docket_atomically(target, [{"symbol": "new"}])
    assert json.loads(target.read_text("utf-8")) == [{"symbol": "new"}]
    assert calls["n"] == 3 and list(tmp_path.glob("*.tmp")) == []


def test_a_reader_that_never_lets_go_fails_as_before(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "external_survivors.json"
    target.write_text('[{"symbol":"old"}]', encoding="utf-8")

    def always_busy(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(merge.os, "replace", always_busy)
    monkeypatch.setattr(merge, "DOCKET_REPLACE_BUDGET_S", 0.05)
    monkeypatch.setattr(merge, "DOCKET_REPLACE_FIRST_WAIT_S", 0.01)
    with pytest.raises(PermissionError):
        merge._write_docket_atomically(target, [{"symbol": "new"}])
    assert json.loads(target.read_text("utf-8")) == [{"symbol": "old"}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_dead_staging_files_are_swept_and_live_ones_kept(tmp_path: Path) -> None:
    import os
    import time
    target = tmp_path / "external_survivors.json"
    dead = tmp_path / ".external_survivors.json.abc.tmp"
    live = tmp_path / ".external_survivors.json.def.tmp"
    other = tmp_path / ".study_bank.json.ghi.tmp"
    for p in (dead, live, other):
        p.write_text("x", encoding="utf-8")
    old = time.time() - merge.DOCKET_ORPHAN_AGE_S - 60
    os.utime(dead, (old, old))
    os.utime(other, (old, old))
    assert merge._sweep_dead_staging(target) == 1
    assert not dead.exists() and live.exists() and other.exists()
