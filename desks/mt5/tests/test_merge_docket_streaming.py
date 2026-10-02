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
    assert json.loads(target.read_text("utf-8")) == rows
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
