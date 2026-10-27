"""judge_volume (2026-10-27): the operator stop lapses, and a shard wave widens on live memory.

Neither lever touches the sealed judge: the stop decides only WHETHER the resident starts a
sweep, and admission decides only HOW MANY shards of a wave run at once. The verdict-identity
proof (serial vs fixed vs admitted waves through the real sealed `_run_shards`) is the bundle's
harness; here the launcher's own contracts are pinned.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from scripts import run_sharded_gauntlet as runner


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "SHARD_PEAKS", tmp_path / "judge_shard_peaks.json")
    monkeypatch.setattr(runner, "RESIDENT_STATE", tmp_path / "JUDGE_RESIDENT.json")
    monkeypatch.setattr(runner, "RESIDENT_MEMORY", tmp_path / "JUDGE_RESIDENT_MEMORY.json")
    monkeypatch.setattr(runner, "RESIDENT_STOP", tmp_path / "RESIDENT_STOP")
    monkeypatch.setattr(runner, "SWEEP_PHASE", tmp_path / "JUDGE_SWEEP_PHASE.json")
    monkeypatch.setattr(runner, "_PHASE_DOC", {})
    monkeypatch.setattr(runner, "HEARTBEAT", tmp_path / "GAUNTLET_HEARTBEAT.json")
    monkeypatch.setattr(runner, "STALL", tmp_path / "GAUNTLET_STALL.json")
    monkeypatch.setattr(runner, "PHASE_TIMES", tmp_path / "judge_phase_times.json")
    monkeypatch.setattr(runner, "_PROGRESS", {})
    monkeypatch.delenv("GAUNTLET_RESIDENT_STOP_TTL_S", raising=False)
    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    monkeypatch.delenv("GAUNTLET_SHARD_ADMISSION", raising=False)
    runner._ABORT.clear()


def _stop(text: str, age_s: float) -> Path:
    p = runner.RESIDENT_STOP
    p.write_text(text, encoding="utf-8")
    t = time.time() - age_s
    os.utime(p, (t, t))
    return p


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


# ------------------------------------------------------------------------ the operator stop
def test_a_fresh_unworded_stop_stops_exactly_as_before() -> None:
    _stop("", 60.0)
    got = runner.resident_stop()
    assert got["stopped"] is True and got["basis"] == "ttl"
    calls: list[int] = []
    runner.resident(sweep=lambda: calls.append(1) or 0, sleep=lambda s: None, clock=_Clock(),
                    max_sweeps=1)
    st = json.loads(runner.RESIDENT_STATE.read_text())
    assert calls == [] and st["status"] == "STOPPED" and "lapses at" in st["why"]


def test_a_forgotten_stop_lapses_and_the_judge_resumes() -> None:
    """The 2026-10-23..27 case: an empty RESIDENT_STOP left behind for 108 hours."""
    p = _stop("", 108 * 3600.0)
    calls: list[int] = []
    runner.resident(sweep=lambda: calls.append(1) or 0, sleep=lambda s: None, clock=_Clock(),
                    max_sweeps=1)
    st = json.loads(runner.RESIDENT_STATE.read_text())
    assert calls == [1] and st["status"] == "DONE"
    assert st["stop_expired"]["expired"] is True
    assert not p.exists()
    assert list(p.parent.glob("RESIDENT_STOP.expired.*")), "the lapsed stop is kept as evidence"


def test_a_hold_never_lapses() -> None:
    _stop("hold -- ledger repair in progress", 30 * 24 * 3600.0)
    got = runner.resident_stop()
    assert got["stopped"] is True and got["basis"] == "hold"
    _stop("INDEFINITE", 30 * 24 * 3600.0)
    assert runner.resident_stop()["stopped"] is True


def test_until_is_read_as_written() -> None:
    _stop("until=2999-01-01T00:00:00Z", 10 * 24 * 3600.0)
    assert runner.resident_stop()["stopped"] is True
    _stop("until=2000-01-01T00:00:00+00:00", 60.0)
    got = runner.resident_stop()
    assert got["stopped"] is False and got["expired"] is True and got["basis"] == "until"


def test_a_malformed_until_falls_back_to_the_ttl() -> None:
    _stop("until=tomorrow", 60.0)
    got = runner.resident_stop()
    assert got["stopped"] is True and got["basis"] == "ttl"


def test_a_non_positive_ttl_restores_never_expires(monkeypatch) -> None:
    monkeypatch.setenv("GAUNTLET_RESIDENT_STOP_TTL_S", "0")
    _stop("", 365 * 24 * 3600.0)
    got = runner.resident_stop()
    assert got["stopped"] is True and got["basis"] == "no_ttl"
    monkeypatch.setenv("GAUNTLET_RESIDENT_STOP_TTL_S", "garbage")
    assert runner._stop_ttl_s() == runner.RESIDENT_STOP_TTL_S


def test_no_file_is_no_stop() -> None:
    assert runner.resident_stop() == {"stopped": False}


# --------------------------------------------------------------------- live shard admission
def _gate(n=15, floor=2, peak=6000.0, avail_start=40_000.0, avail=lambda: 40_000.0,
          rss=lambda phase: [], logs: Path | None = None) -> runner._Admission:
    logs = logs or Path("/nonexistent-logs")
    return runner._Admission(n, "build", floor, logs, "inv", peak, avail_start, avail=avail,
                             rss=rss)


def _widest(g: runner._Admission) -> int:
    running = 0
    while running < g.n and g.admits(running):
        running += 1
    return running


def test_with_no_receipt_of_its_own_the_wave_is_exactly_parallelism(monkeypatch) -> None:
    """Before this wave has measured anything the gate is `_parallelism`'s formula, unchanged."""
    monkeypatch.setattr(runner, "_available_mb", lambda: 40_000.0)
    for peak in (1500.0, 4000.0, 6000.0, 9000.0, 20_000.0, 50_000.0):
        runner.SHARD_PEAKS.write_text(json.dumps({"build": [peak]}))
        floor = runner._parallelism(15, "build")
        g = _gate(floor=floor, peak=peak)
        assert _widest(g) == floor, peak


def test_the_wave_widens_on_its_own_smaller_peaks(tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "inv-build-0-attempt-0.peak.json").write_text(json.dumps({"peak_mb": 2000.0}))
    # historic 20 GB peak pinned the floor at 1; this wave's shards measure 2 GB.
    g = _gate(floor=1, peak=20_000.0, avail_start=40_000.0, logs=logs)
    # room = 40,000 - running x 2,500 - 2,500 >= 20,000  ->  running <= 7
    assert _widest(g) == 8
    assert g.width_max == 8 and g.last["estimate_basis"] == "this_wave_peak_x_margin"


def test_a_running_shard_above_the_estimate_is_charged_what_it_holds(tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "inv-build-0-attempt-0.peak.json").write_text(json.dumps({"peak_mb": 1000.0}))
    g = _gate(floor=1, peak=20_000.0, logs=logs, avail=lambda: 30_000.0,
              rss=lambda phase: [10_000.0])
    # est = 10,000 x 1.25 (the running rss is in the estimate); room = 30,000 + 10,000 - 12,500
    # - 12,500 = 15,000 < 20,000 reserve: refused.
    assert g.admits(1) is False


def test_never_below_the_floor_and_never_above_n() -> None:
    g = _gate(floor=3, avail=lambda: 0.0)
    assert [g.admits(r) for r in range(3)] == [True, True, True]
    assert g.admits(3) is False
    g = _gate(n=4, floor=1, peak=1.0)
    assert _widest(g) == 4


def test_an_unread_box_never_widens() -> None:
    g = _gate(floor=2, peak=1.0, avail=lambda: None)
    assert _widest(g) == 2


def test_the_gate_is_off_for_an_operator_cap_or_the_switch(monkeypatch, tmp_path) -> None:
    runner.SHARD_PEAKS.write_text(json.dumps({"build": [4000.0]}))
    monkeypatch.setattr(runner, "_available_mb", lambda: 40_000.0)
    assert runner._admission_for(15, "build", 5, tmp_path, "i") is not None
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "3")
    assert runner._admission_for(15, "build", 3, tmp_path, "i") is None
    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY")
    monkeypatch.setenv("GAUNTLET_SHARD_ADMISSION", "0")
    assert runner._admission_for(15, "build", 5, tmp_path, "i") is None
    monkeypatch.delenv("GAUNTLET_SHARD_ADMISSION")
    assert runner._admission_for(5, "build", 5, tmp_path, "i") is None      # already full width
    runner.SHARD_PEAKS.unlink()
    assert runner._admission_for(15, "build", 2, tmp_path, "i") is None     # never measured


def test_admitted_wave_runs_every_shard_once_in_order_within_the_gate() -> None:
    lock = threading.Lock()
    live, peak_live, seen = [0], [0], []

    def attempted(k: int):
        with lock:
            live[0] += 1
            peak_live[0] = max(peak_live[0], live[0])
            seen.append(k)
        time.sleep(0.01 * ((k * 5) % 7))
        with lock:
            live[0] -= 1
        return k, (RuntimeError("x") if k == 4 else None)

    class _Three:
        phase = "build"

        def admits(self, running: int) -> bool:
            return running < 3

    got = runner._admitted_wave(12, attempted, _Three(), aborted=lambda: False, poll_s=0.005)
    assert [k for k, _ in got] == list(range(12))
    assert isinstance(got[4][1], RuntimeError) and all(e is None for k, e in got if k != 4)
    assert sorted(seen) == list(range(12)) and peak_live[0] <= 3


def test_an_aborted_wave_starts_the_rest_without_waiting() -> None:
    class _Never:
        phase = "build"

        def admits(self, running: int) -> bool:
            return running < 1

    t0 = time.monotonic()
    got = runner._admitted_wave(6, lambda k: (time.sleep(0.2), (k, None))[1], _Never(),
                                aborted=lambda: True, poll_s=10.0)
    assert [k for k, _ in got] == list(range(6)) and time.monotonic() - t0 < 5.0


def test_dispatch_widens_live_and_still_runs_every_shard_once(monkeypatch, tmp_path) -> None:
    runner.SHARD_PEAKS.write_text(json.dumps({"build": [30_000.0]}))
    monkeypatch.setattr(runner, "_available_mb", lambda: 40_000.0)   # floor 1
    monkeypatch.setattr(runner, "_wave_children_rss_mb", lambda phase: [])
    lock = threading.Lock()
    live, peak_live, ran = [0], [0], []

    def fake_run(argv, **kw):
        k = int(argv[-2])
        with lock:
            live[0] += 1
            peak_live[0] = max(peak_live[0], live[0])
            ran.append(k)
        Path(kw["env"]["GAUNTLET_PEAK_RECEIPT"]).write_text(json.dumps({"peak_mb": 1000.0}))
        time.sleep(0.05)
        with lock:
            live[0] -= 1

    monkeypatch.setattr(runner, "run", fake_run)
    monkeypatch.setattr(runner, "SHARD_ADMIT_POLL_S", 0.01)
    runner.dispatch(tmp_path / "shards", 8, "build")
    assert sorted(ran) == list(range(8))
    assert peak_live[0] > 1, "this wave's 1 GB receipts must widen it past the 30 GB floor"
    assert runner._PROGRESS["admission"]["floor"] == 1
    assert runner._PROGRESS["admission"]["widest"] >= peak_live[0]
