"""The study bank and event lane are written whole or not at all: streamed to a staging file and
renamed into place, never truncated in place (MT5-MergeDocket hung 17.5 h at "study bank")."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import merge_hypotheses as mh  # noqa: E402


def test_rows_land_whole_and_leave_no_staging(tmp_path):
    path = tmp_path / "study_bank.json"
    rows = [{"family": "f", "i": i} for i in range(500)]
    mh._write_rows_atomic(path, rows)
    assert json.loads(path.read_text("utf-8")) == rows
    assert not list(tmp_path.glob(".study_bank.json.*.tmp"))


def test_a_failed_write_keeps_the_old_bank(tmp_path, monkeypatch):
    path = tmp_path / "study_bank.json"
    mh._write_rows_atomic(path, [{"keep": 1}])

    def dies_mid_stream(rows, handle, **_k):
        handle.write('[{"x"')
        raise RuntimeError("serialiser died mid-stream")

    monkeypatch.setattr(mh.json, "dump", dies_mid_stream)
    with pytest.raises(RuntimeError):
        mh._write_rows_atomic(path, [{"x": 1}])
    monkeypatch.undo()
    assert json.loads(path.read_text("utf-8")) == [{"keep": 1}]
    assert not list(tmp_path.glob(".study_bank.json.*.tmp"))


def test_both_lane_writers_use_it():
    src = (DESK / "research" / "merge_hypotheses.py").read_text("utf-8")
    assert "_write_rows_atomic(STUDY_BANK, study)" in src
    assert "_write_rows_atomic(EVENT_LANE, off_lane)" in src
    assert "STUDY_BANK.write_text(" not in src and "EVENT_LANE.write_text(" not in src
