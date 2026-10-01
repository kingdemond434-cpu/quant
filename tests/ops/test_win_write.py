"""Writes on the trading box must survive Windows sharing violations.

The last shadow census the box published (2026-09-16T16:37Z) was FAILED on two PermissionError 13
in-place overwrites -- XAUUSD_M1.parquet and external_shadow_state.json -- while the forward
clocks themselves had advanced, so MT5-Shadow exited 1 every run. POSIX never reproduces this, so
these tests simulate the refusal the way Windows raises it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from libs.ops import win_write

ROOT = Path(__file__).resolve().parents[2]


def _refuse(*_a, **_k):
    raise PermissionError(13, "Permission denied")


def test_plain_write_is_atomic_and_leaves_no_temp(tmp_path: Path) -> None:
    p = tmp_path / "x.json"
    win_write.write_text_resilient(p, '{"a": 1}')
    assert json.loads(p.read_text("utf-8")) == {"a": 1}
    assert [q.name for q in tmp_path.iterdir()] == ["x.json"]


def test_a_refused_rename_falls_back_to_writing_in_place(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "state.json"
    p.write_text("{}", "utf-8")
    monkeypatch.setattr(win_write.os, "replace", _refuse)
    monkeypatch.setattr(win_write.time, "sleep", lambda s: None)
    win_write.write_bytes_resilient(p, b'{"k": 2}')
    assert p.read_bytes() == b'{"k": 2}'
    assert [q.name for q in tmp_path.iterdir()] == ["state.json"]


def test_a_total_refusal_is_raised_not_swallowed(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "state.json"
    monkeypatch.setattr(win_write.os, "replace", _refuse)
    monkeypatch.setattr(win_write.time, "sleep", lambda s: None)
    real_open = open

    def refusing_open(file, mode="r", *a, **k):
        if str(file) == str(p) and "w" in mode:
            raise PermissionError(13, "Permission denied")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr("builtins.open", refusing_open)
    with pytest.raises(PermissionError):
        win_write.write_bytes_resilient(p, b"x", attempts=2)
    assert not list(tmp_path.glob(".*.tmp")), "a failed write left its temp file behind"


def test_external_shadow_survives_a_held_state_file(tmp_path: Path, monkeypatch) -> None:
    """The 2026-09-16 `external_state_reconcile` failure, reproduced and survived."""
    sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))
    import external_shadow
    state = tmp_path / "external_shadow_state.json"
    state.write_text(json.dumps({"external.X": {"status": "ACTIVE"}}), "utf-8")
    monkeypatch.setattr(external_shadow, "STATE", state)
    monkeypatch.setattr(external_shadow, "CERTS", tmp_path / "none.json")
    monkeypatch.setattr(win_write.os, "replace", _refuse)
    monkeypatch.setattr(win_write.time, "sleep", lambda s: None)
    assert external_shadow.main() == 0
    doc = json.loads(state.read_text("utf-8"))
    assert doc["external.X"]["status"] == "RETIRED_UNRECONSTRUCTIBLE"


def test_the_scalp_refresh_no_longer_overwrites_bars_in_place() -> None:
    src = (ROOT / "desks/mt5/research/shadow_cycle.py").read_text("utf-8")
    body = src[src.index("def _refresh_scalp_bars"):src.index("def _read(")]
    assert '.to_parquet(out_dir' not in body, "an in-place parquet overwrite is back"
    assert "write_bytes_resilient" in body and "write_text_resilient" in body
