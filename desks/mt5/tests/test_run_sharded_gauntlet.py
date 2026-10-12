from __future__ import annotations

import sys

import pytest

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
