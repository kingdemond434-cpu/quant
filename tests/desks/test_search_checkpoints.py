"""Both search legs must leave an artifact when they are killed mid-run.

WHY THIS TEST EXISTS. edge_search and orthogonal_sweep each built their whole result and wrote
it in a single `write_text` after the symbol loop. The external pipeline allots each a 20-minute
remote stage that `timeout ssh` enforces by killing the ssh CLIENT, which kills the remote
process -- so a run longer than its slot left the artifact untouched no matter how much work it
had done. Measured 2026-09-03: edge_search ran 37 minutes without writing a byte,
edge_search_results.json was 27.8 hours stale and orthogonal_candidates.json 15.5, with both
jobs alive the whole time. The research-health fence could only describe that as "alive but has
produced nothing", which is true and gives no way to find the cause.

The per-cell cursor advanced every run, so the searches genuinely did the work every hour and had
nothing to show for it. That is structural: a producer that writes only on completion cannot
produce under a timeout shorter than its runtime, and no amount of memory or fresh code fixes it.

These tests pin the three properties that make the fix real, because all three were absent:
an artifact exists BEFORE the loop ends, it says so (`partial`), and a kill during the write
cannot leave a torn file for merge_hypotheses to parse.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desks" / "mt5"))

from research import edge_search, orthogonal_sweep


def test_edge_search_writes_a_partial_artifact_before_the_loop_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "edge_search_results.json"
    monkeypatch.setattr(edge_search, "OUT", out)
    edge_search._emit(datetime.now(UTC), ["EURUSD", "XAUUSD"], [{"symbol": "EURUSD"}],
                      [], [], 1234, 0, partial=True)

    assert out.exists(), "a mid-run checkpoint must leave the artifact on disk"
    doc = json.loads(out.read_text("utf-8"))
    assert doc["partial"] is True, "an interrupted run must SAY it was interrupted (L1.28a)"
    assert doc["symbols_completed"] == 1
    assert doc["total_trials"] == 1234
    assert not list(tmp_path.glob("*.tmp")), "the temp file must be replaced, never left behind"


def test_edge_search_marks_a_finished_run_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "edge_search_results.json"
    monkeypatch.setattr(edge_search, "OUT", out)
    edge_search._emit(datetime.now(UTC), ["EURUSD"], [{"symbol": "EURUSD"}], [], [], 7, 0,
                      partial=False)
    assert json.loads(out.read_text("utf-8"))["partial"] is False


def test_edge_search_checkpoint_never_leaves_a_torn_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader that arrives mid-write must see the PREVIOUS artifact, never half of this one."""
    out = tmp_path / "edge_search_results.json"
    monkeypatch.setattr(edge_search, "OUT", out)
    edge_search._emit(datetime.now(UTC), ["A"], [{"symbol": "A"}], [], [], 1, 0, partial=True)
    first = json.loads(out.read_text("utf-8"))

    import os as _os

    def _die(src: str, dst: str) -> None:
        raise RuntimeError("killed mid-write")

    monkeypatch.setattr(_os, "replace", _die)
    with pytest.raises(RuntimeError):
        edge_search._emit(datetime.now(UTC), ["A", "B"], [{"symbol": "A"}, {"symbol": "B"}],
                          [], [], 2, 0, partial=True)
    assert json.loads(out.read_text("utf-8")) == first, (
        "a kill during the write must leave the previous complete artifact intact")


def test_orthogonal_sweep_writes_a_partial_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "orthogonal_candidates.json"
    monkeypatch.setattr(orthogonal_sweep, "OUT", out)
    report = orthogonal_sweep._build_report(["EURUSD"], {"fam": 1}, {}, {}, {}, [])
    orthogonal_sweep._write_report(report, partial=True)

    assert out.exists()
    doc = json.loads(out.read_text("utf-8"))
    assert doc["partial"] is True
    assert doc["symbols"] == 1
    assert not list(tmp_path.glob("*.tmp"))


def test_orthogonal_sweep_marks_a_finished_run_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "orthogonal_candidates.json"
    monkeypatch.setattr(orthogonal_sweep, "OUT", out)
    orthogonal_sweep._write_report(
        orthogonal_sweep._build_report([], {}, {}, {}, {}, []), partial=False)
    assert json.loads(out.read_text("utf-8"))["partial"] is False
