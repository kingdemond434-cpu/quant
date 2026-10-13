from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_sharded_gauntlet as runner


def test_shard_count_falls_closed_and_honours_measurement(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_SHARDS", raising=False)
    assert runner._shards() == 1
    monkeypatch.setenv("GAUNTLET_SHARDS", "7")
    assert runner._shards() == 7
    monkeypatch.setenv("GAUNTLET_SHARDS", "broken")
    assert runner._shards() == 1


def test_retry_count_falls_closed_and_honours_measurement(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_SHARD_RETRIES", raising=False)
    assert runner._retry_attempts() == 2
    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "4")
    assert runner._retry_attempts() == 4
    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "broken")
    assert runner._retry_attempts() == 2


def test_parallelism_is_bounded_and_configurable(monkeypatch) -> None:
    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    assert runner._parallelism(15) == 2
    assert runner._parallelism(1) == 1
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "4")
    assert runner._parallelism(15) == 4
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "99")
    assert runner._parallelism(15) == 15
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "broken")
    assert runner._parallelism(15) == 1


def test_initial_wave_limits_live_children_without_losing_partitions(monkeypatch, tmp_path):
    import threading
    import time

    active = peak = 0
    completed = []
    lock = threading.Lock()

    def child(argv, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            completed.append(int(argv[-2]))
            active -= 1

    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    monkeypatch.setattr(runner, "run", child)
    runner.dispatch(tmp_path, 7, "build")
    assert peak == 2
    assert sorted(completed) == list(range(7))


def test_dispatch_runs_every_shard_once(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))

    monkeypatch.setattr(runner, "run", fake_run)
    runner.dispatch(tmp_path, 4, "build")
    assert sorted(int(argv[-2]) for argv, _ in calls) == [0, 1, 2, 3]
    assert all(argv[0] == sys.executable and argv[-1] == "build" for argv, _ in calls)
    assert all(kwargs["check"] is True and kwargs["capture_output"] is False
               for _, kwargs in calls)


def test_dispatch_retries_only_failed_shards_after_parallel_wave(monkeypatch, tmp_path) -> None:
    calls: list[int] = []
    failures_left = {1: 1, 3: 2}

    def fake_run(argv, **kwargs):
        shard = int(argv[-2])
        calls.append(shard)
        if failures_left.get(shard, 0):
            failures_left[shard] -= 1
            raise RuntimeError(f"transient shard {shard}")

    monkeypatch.setattr(runner, "run", fake_run)
    runner.dispatch(tmp_path, 4, "build")

    assert calls.count(0) == 1
    assert calls.count(1) == 2
    assert calls.count(2) == 1
    assert calls.count(3) == 3


def test_dispatch_propagates_a_failed_shard(monkeypatch, tmp_path) -> None:
    def fake_run(argv, **kwargs):
        if argv[-2] == "2":
            raise RuntimeError("shard failed")

    monkeypatch.setattr(runner, "run", fake_run)
    with pytest.raises(RuntimeError, match="shard 2 failed after 3 attempt"):
        runner.dispatch(tmp_path, 4, "rule")


def test_actual_child_stderr_survives_retries_and_shard_cleanup(monkeypatch, tmp_path):
    from libs.ops.proctree import run as child_run

    shard_dir = tmp_path / "shards"
    shard_dir.mkdir()
    attempts = []

    def child(argv, **kwargs):
        attempts.append(int(argv[-2]))
        return child_run([sys.executable, "-c",
                          "import sys; print('real child error', file=sys.stderr); sys.exit(7)"],
                         **kwargs)

    monkeypatch.setenv("GAUNTLET_SHARD_RETRIES", "1")
    monkeypatch.setattr(runner, "run", child)
    with pytest.raises(RuntimeError, match="refusing partial merge") as failed:
        runner.dispatch(shard_dir, 1, "build")
    shard_dir.rmdir()
    receipts = list((tmp_path / "shards-logs").glob("*.log"))
    assert len(receipts) == 2
    assert attempts == [0, 0]
    assert all("real child error" in p.read_text() for p in receipts)
    assert "child log=" in str(failed.value.__cause__)
