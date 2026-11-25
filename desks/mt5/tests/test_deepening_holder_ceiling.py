"""A hung deepening holder ends itself, so the single-flight lock cannot go dark for hours."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deepening_worker as dw  # noqa: E402


def test_the_ceiling_fires_past_twice_the_budget_with_the_exit_code() -> None:
    fired = threading.Event()
    got: list[int] = []

    def _exit(rc: int) -> None:
        got.append(rc)
        fired.set()

    t = dw.arm_holder_ceiling(0.01, exit_fn=_exit)
    assert t.daemon and fired.wait(2.0)
    assert got == [dw.HOLDER_EXIT_RC]


def test_a_run_that_finishes_cancels_the_ceiling() -> None:
    got: list[int] = []
    t = dw.arm_holder_ceiling(5.0, exit_fn=got.append)
    t.cancel()
    t.join(1.0)
    assert got == []


def test_the_ceiling_is_the_same_bound_callers_use_as_stale() -> None:
    src = (DESK / "research" / "deepening_worker.py").read_text("utf-8")
    assert "stale_after = RUN_BUDGET_SEC * 2.0" in src
    assert dw.HOLDER_CEILING_FACTOR == 2.0
    assert "ceiling = arm_holder_ceiling()" in src and "ceiling.cancel()" in src


def test_the_swarm_launches_one_single_flight_worker_with_parallel_seats() -> None:
    src = (DESK.parent.parent / "ops" / "convert_swarm.py").read_text("utf-8")
    assert "for model in models[:1]:" in src
    assert 'env["DEEPEN_SEAT_WORKERS"] = str(max(1, len(models)))' in src
    assert 'env["OPENROUTER_MODEL"]' not in src


def test_an_unreadable_history_is_moved_aside_never_overwritten_as_empty(tmp_path: Path) -> None:
    out = tmp_path / "deepened_candidates.json"
    out.write_text('{"candidates": [{"id": 1}, {"id"', encoding="utf-8")   # truncated mid-write
    assert dw.read_prior_candidates(out) == []
    aside = list(tmp_path.glob("deepened_candidates.json.corrupt-*"))
    assert len(aside) == 1 and aside[0].read_text("utf-8").startswith('{"candidates"')
    assert not out.exists()


def test_the_history_is_written_atomically_and_read_back(tmp_path: Path) -> None:
    out = tmp_path / "deepened_candidates.json"
    dw.write_candidates_atomic(out, {"candidates": [{"id": 1}]})
    assert dw.read_prior_candidates(out) == [{"id": 1}]
    assert list(tmp_path.glob("*.tmp")) == []
    src = (DESK / "research" / "deepening_worker.py").read_text("utf-8")
    assert "OUT.write_text(" not in src


def test_a_history_that_cannot_be_moved_aside_is_left_byte_identical(
        tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "deepened_candidates.json"
    raw = b'{"candidates": [{"id": 1}, {"id"'
    out.write_bytes(raw)

    def _locked(src, dst):  # type: ignore[no-untyped-def]
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(dw.os, "replace", _locked)
    assert dw.read_prior_candidates(out) is None          # the caller writes nothing this run
    monkeypatch.undo()
    assert out.read_bytes() == raw
    src = (DESK / "research" / "deepening_worker.py").read_text("utf-8")
    assert "if prior is not None:\n        write_candidates_atomic(OUT" in src


def test_the_skip_path_spills_the_runs_own_rows_to_a_side_file() -> None:
    src = (DESK / "research" / "deepening_worker.py").read_text("utf-8")
    skip = src.split("if prior is not None:\n        write_candidates_atomic(OUT, run_doc)")[1]
    assert ".pending-" in skip.split("\n\n")[0] and "write_candidates_atomic(side, run_doc)" in skip
