from __future__ import annotations

import io
import json
import pickle
import sys
import threading
import time
from pathlib import Path

import pytest

from scripts import run_sharded_gauntlet as runner


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path) -> None:
    """Every test writes its model to a temp file, never the box's state."""
    monkeypatch.setattr(runner, "MODEL_FILE", tmp_path / "judging_shard_memory.json")
    monkeypatch.setattr(runner, "SHARD_DIR", tmp_path / "shards")
    monkeypatch.setattr(runner, "free_mb", lambda: 100_000.0)
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "4")
    runner.RUN.clear()


def _ok(calls: list[tuple[int, dict[str, str]]], peak: float = 1000.0):
    lock = threading.Lock()

    def fake(argv: list[str], env: dict[str, str]) -> tuple[int, float]:
        with lock:
            calls.append((int(argv[-2]), env))
        return 0, peak
    return fake


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


def test_dispatch_runs_every_shard_once_with_per_child_env(tmp_path) -> None:
    calls: list[tuple[int, dict[str, str]]] = []
    runner.dispatch(tmp_path, 4, "build", runner=_ok(calls))
    assert sorted(k for k, _ in calls) == [0, 1, 2, 3]
    for _k, env in calls:
        # one worker and one BLAS thread per child; the CHILD's budget, not the sweep's
        assert env["GAUNTLET_WORKERS"] == "1" and env["OMP_NUM_THREADS"] == "1"
        assert int(env["GAUNTLET_MEMORY_BUDGET_MB"]) == int((0.8 * 100_000 - 6144) / 4)


def test_dispatch_runs_only_the_pending_shards_it_is_handed(tmp_path) -> None:
    calls: list[tuple[int, dict[str, str]]] = []
    runner.dispatch(tmp_path, 6, "rule", ks=[4, 1], runner=_ok(calls))
    assert sorted(k for k, _ in calls) == [1, 4]


def test_dispatch_retries_only_failed_shards_after_the_wave(tmp_path) -> None:
    calls: list[int] = []
    failures_left = {1: 1, 3: 2}
    lock = threading.Lock()

    def fake(argv, env):
        shard = int(argv[-2])
        with lock:
            calls.append(shard)
            if failures_left.get(shard, 0):
                failures_left[shard] -= 1
                return 1, 500.0
        return 0, 900.0

    runner.dispatch(tmp_path, 4, "build", runner=fake)
    assert calls.count(0) == 1 and calls.count(2) == 1
    assert calls.count(1) == 2 and calls.count(3) == 3


def test_dispatch_propagates_a_failed_shard(tmp_path) -> None:
    def fake(argv, env):
        return (1 if argv[-2] == "2" else 0), 100.0

    with pytest.raises(RuntimeError, match="shard 2 failed after 3 attempt"):
        runner.dispatch(tmp_path, 4, "rule", runner=fake)


def test_admission_never_starts_more_than_measured_memory_allows(tmp_path, monkeypatch) -> None:
    """Room for two predicted peaks: two shards run at once even with a concurrency cap of 4."""
    running = {"now": 0, "max": 0}
    lock = threading.Lock()

    def fake(argv, env):
        with lock:
            running["now"] += 1
            running["max"] = max(running["max"], running["now"])
        time.sleep(0.05)
        with lock:
            running["now"] -= 1
        return 0, 4000.0

    def measure() -> float:
        with lock:
            return runner.RESERVE_MB + 4096.0 * (2 - running["now"]) + 1.0

    adm = runner.Admission({}, measure=measure)
    adm_acquire = runner.Admission.acquire

    def acquire(self, need, poll_s=0.01):
        return adm_acquire(self, need, poll_s=0.01)

    monkeypatch.setattr(runner.Admission, "acquire", acquire)
    runner.dispatch(tmp_path, 6, "build", runner=fake, admission=adm)
    assert running["max"] <= 2


def test_admission_always_lets_one_shard_run() -> None:
    adm = runner.Admission({}, measure=lambda: 0.0)
    adm.acquire(10_000.0)           # nothing running: admitted although the box looks full
    assert adm.running == 1
    adm.release(123.0)
    assert adm.seen_peaks == [123.0]


def test_the_model_learns_mb_per_cell_and_sizes_the_next_shard_count(tmp_path) -> None:
    sd = tmp_path / "sd"
    sd.mkdir()
    for k in range(2):
        with open(sd / f"plan_{k}.pkl", "wb") as fh:
            pickle.dump([(i, {"sym": "X"}) for i in range(1000)], fh)
    runner.RUN.update(run_id="r1", planned_cells=2000)
    calls: list[tuple[int, dict[str, str]]] = []
    runner.dispatch(sd, 2, "build", runner=_ok(calls, peak=2350.0))
    model = runner.load_model()
    rec = [s for s in model["runs"][-1]["shards"] if s["ok"]]
    assert len(rec) == 2 and all(s["cells"] == 1000 for s in rec)
    pc = runner.per_cell_mb(model)
    assert pc is not None and 1.9 < pc < 2.0          # (2350 - ~350 base) / 1000
    # 585k cells at ~2 MB/cell need far more than two shards in 100 GB at 4 at a time
    n, why = runner.derive_shards(model, 584_979, 4, 2, 100_000.0)
    assert n > 2 and "MB/cell" in why
    # but an unfinished epoch holds its own count, so its finished shards stay valid
    n2, why2 = runner.derive_shards(model, 584_979, 4, 2, 100_000.0, {"n": 15})
    assert n2 == 15 and "resume" in why2
    # and with nothing measured, the published count stands
    assert runner.derive_shards({}, 584_979, 4, 7, 100_000.0)[0] == 7


def test_the_plan_size_is_read_off_the_judge_s_own_line() -> None:
    tap = runner._PlanTap(io.StringIO())
    tap.write("SHARDED SWEEP: 584979 planned cell(s) across 15 shard(s)\n")
    assert runner.RUN["planned_cells"] == 584979


def test_decide_reads_an_unfinished_epoch(tmp_path, monkeypatch) -> None:
    (tmp_path / "shards").mkdir()
    (tmp_path / "shards" / "epoch.json").write_text(json.dumps({"n": 9, "token": "t"}), "utf-8")
    monkeypatch.setenv("GAUNTLET_SHARDS", "15")
    assert runner.decide({})["n_shards"] == 9


def test_child_env_never_exports_a_budget_below_the_declared_floor() -> None:
    assert runner.child_env(10.0)["GAUNTLET_MEMORY_BUDGET_MB"] == "1200"
    assert "GAUNTLET_MEMORY_BUDGET_MB" not in runner.child_env(None) or \
        runner.child_env(None)["GAUNTLET_MEMORY_BUDGET_MB"] == \
        __import__("os").environ.get("GAUNTLET_MEMORY_BUDGET_MB")


def test_run_child_measures_a_real_process(tmp_path) -> None:
    rc, peak = runner.run_child([sys.executable, "-c", "import time; time.sleep(2.5)"],
                                dict(__import__("os").environ))
    assert rc == 0
    if runner.psutil is not None:
        assert peak > 0


def test_model_file_is_desk_state() -> None:
    from libs.ops.release import is_state_path
    rel = Path("desks/mt5/data/judging_shard_memory.json")
    assert is_state_path(str(rel))
