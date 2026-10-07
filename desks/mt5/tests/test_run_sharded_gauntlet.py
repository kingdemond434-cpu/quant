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
    monkeypatch.setattr(runner, "total_mb", lambda: 131_072.0)
    monkeypatch.setattr(runner, "BLOCKED_FILE", tmp_path / "BLOCKED_SHARD_OOM.json")
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

    def acquire(self, need, poll_s=0.01, key=None, wait_s=None):
        return adm_acquire(self, need, poll_s=0.01, key=key)

    monkeypatch.setattr(runner.Admission, "acquire", acquire)
    runner.dispatch(tmp_path, 6, "build", runner=fake, admission=adm)
    assert running["max"] <= 2


def test_an_unmeasurable_host_still_runs_one_shard() -> None:
    adm = runner.Admission({}, measure=lambda: None)
    assert adm.acquire(10_000.0, wait_s=0) is True      # psutil absent: the old fallback
    assert adm.running == 1
    adm.release(123.0)
    assert adm.seen_peaks == [123.0]


def test_a_box_with_no_room_launches_nothing_even_first() -> None:
    """8 GB cold start: the first shard no longer starts unconditionally."""
    adm = runner.Admission({}, measure=lambda: 0.0, reserve=0.0)
    assert adm.acquire(10_000.0, poll_s=0.01, wait_s=0.05) is False
    assert adm.running == 0


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


def test_child_env_exports_the_measured_room_with_no_fixed_floor() -> None:
    # it was floored at 1200 MB whatever the box had free; admission now guarantees the room
    assert runner.child_env(500.0)["GAUNTLET_MEMORY_BUDGET_MB"] == "500"
    assert "GAUNTLET_MEMORY_BUDGET_MB" not in runner.child_env(None) or \
        runner.child_env(None)["GAUNTLET_MEMORY_BUDGET_MB"] == \
        __import__("os").environ.get("GAUNTLET_MEMORY_BUDGET_MB")


def test_run_child_measures_a_real_process(tmp_path) -> None:
    samples: list[float] = []
    rc, peak, info = runner.run_child([sys.executable, "-c", "import time; time.sleep(2.5)"],
                                      dict(__import__("os").environ), on_sample=samples.append)
    assert rc == 0 and info["oom"] is False
    if runner.psutil is not None:
        assert peak > 0 and samples


def test_run_child_names_a_death_by_memory() -> None:
    """D3: numpy's _ArrayMemoryError / MemoryError in the child is recognised by name."""
    code = "import sys; sys.stderr.write('numpy.core._exceptions._ArrayMemoryError: Unable to " \
           "allocate 9.1 GiB\\n'); raise SystemExit(1)"
    rc, _peak, info = runner.run_child([sys.executable, "-c", code],
                                       dict(__import__("os").environ))
    assert rc == 1 and info["oom"] is True


def _model_with(per_cell: float) -> dict:
    return {"runs": [{"shards": [{"ok": True, "per_cell_mb": per_cell}]}]}


def test_free_memory_that_never_falls_still_does_not_over_admit(tmp_path, monkeypatch) -> None:
    """D1, the measured failure: 60 GB free that never drops (a just-started shard has not grown)
    and ~9 GB peaks. The old rule launched every shard at once; the outstanding growth of the
    running shards is now charged, so at most (60,000 - reserve) / 9,000 run together."""
    running = {"now": 0, "max": 0}
    lock = threading.Lock()

    def fake(argv, env):
        with lock:
            running["now"] += 1
            running["max"] = max(running["max"], running["now"])
        time.sleep(0.05)
        with lock:
            running["now"] -= 1
        return 0, 9000.0

    sd = tmp_path / "sd"
    sd.mkdir()
    for k in range(15):
        with open(sd / f"plan_{k}.pkl", "wb") as fh:
            pickle.dump([(i, {"sym": "X"}) for i in range(1000)], fh)
    runner.RUN.update(run_id="r", planned_cells=15_000)
    monkeypatch.setenv("GAUNTLET_SHARD_CONCURRENCY", "15")
    adm = runner.Admission(_model_with(8.6), measure=lambda: 60_000.0)
    acquire = runner.Admission.acquire
    monkeypatch.setattr(runner.Admission, "acquire",
                        lambda self, need, poll_s=0.01, key=None, wait_s=None:
                        acquire(self, need, 0.01, key))
    runner.dispatch(sd, 15, "build", runner=fake, admission=adm)
    assert 1 <= running["max"] <= int((60_000 - adm.reserve) // 9000)


def test_with_no_model_one_shard_runs_first_then_admission_widens(tmp_path, monkeypatch) -> None:
    order: list[tuple[str, int]] = []
    lock = threading.Lock()

    def fake(argv, env):
        k = int(argv[-2])
        with lock:
            order.append(("start", k))
        time.sleep(0.05)
        with lock:
            order.append(("end", k))
        return 0, 1000.0

    acquire = runner.Admission.acquire
    monkeypatch.setattr(runner.Admission, "acquire",
                        lambda self, need, poll_s=0.01, key=None, wait_s=None:
                        acquire(self, need, 0.01, key))
    adm = runner.Admission({}, measure=lambda: 100_000.0)
    runner.dispatch(tmp_path, 4, "build", runner=fake, admission=adm)
    # nothing else starts until the first shard has ended and its peak is known
    assert order[0][0] == "start" and order[1] == ("end", order[0][1])
    starts = [i for i, e in enumerate(order) if e[0] == "start"]
    ends = [i for i, e in enumerate(order) if e[0] == "end"]
    assert any(s < e for s in starts[2:] for e in ends[1:])   # then several run together


def test_a_crashed_dispatcher_thread_is_a_failure_not_a_success(tmp_path, monkeypatch) -> None:
    """D5: a fault outside the child (here in the prediction) used to kill the thread silently and
    read as success. It is the shard's failure now, retried, and fatal if it persists."""
    calls: list[int] = []

    def fake(argv, env):
        calls.append(int(argv[-2]))
        return 0, 100.0

    adm = runner.Admission({}, measure=lambda: 100_000.0)
    real = adm.predict

    def predict(base, cells):
        if cells is None and threading.current_thread().name.endswith("-2"):
            raise ValueError("synthetic bookkeeping fault")
        return real(base, cells)

    monkeypatch.setattr(adm, "predict", predict)
    runner.dispatch(tmp_path, 4, "build", runner=fake, admission=adm)
    assert sorted(calls) == [0, 1, 2, 3]          # shard 2 ran -- on its serial retry
    rec = [r for r in runner.RUN["shards"] if r["k"] == 2]
    assert rec[0]["ok"] is False and "synthetic" in rec[0]["error"] and rec[-1]["ok"] is True

    def always(base, cells):
        raise ValueError("persistent fault")

    monkeypatch.setattr(adm, "predict", always)
    with pytest.raises(RuntimeError, match="refusing partial merge"):
        runner.dispatch(tmp_path, 2, "rule", runner=fake, admission=adm)


def test_a_memory_death_lowers_concurrency_feeds_the_model_and_retries_alone(tmp_path) -> None:
    """D3: ArrayMemoryError/MemoryError per shard: its peak goes into the model, this run's
    concurrency is lowered, and the shard is retried alone."""
    died = {1: True}
    lock = threading.Lock()

    def fake(argv, env):
        k = int(argv[-2])
        with lock:
            if died.pop(k, False):
                return 1, 9000.0, {"oom": True}
        return 0, 2000.0, {"oom": False}

    sd = tmp_path / "sd"
    sd.mkdir()
    for k in range(4):
        with open(sd / f"plan_{k}.pkl", "wb") as fh:
            pickle.dump([(i, {"sym": "X"}) for i in range(1000)], fh)
    runner.RUN.update(run_id="r", planned_cells=4000)
    adm = runner.Admission(_model_with(1.0), measure=lambda: 100_000.0)
    runner.dispatch(sd, 4, "build", runner=fake, admission=adm)
    recs = [r for r in runner.RUN["shards"] if r["k"] == 1]
    assert recs[0]["oom"] is True and recs[0]["ok"] is False and recs[0]["per_cell_mb"] > 8
    assert recs[-1]["ok"] is True and recs[-1]["serial_retry"] is True
    assert adm.limit is not None and adm.limit >= 1
    assert 9000.0 in adm.seen_peaks
    # the failed shard's measurement is in the model the next run sizes from
    assert runner.per_cell_mb(runner.load_model()) > 8


def test_model_file_is_desk_state() -> None:
    from libs.ops.release import is_state_path
    rel = Path("desks/mt5/data/judging_shard_memory.json")
    assert is_state_path(str(rel))


def test_run_gauntlet_cmd_passes_its_arguments_to_this_launcher() -> None:
    cmd = (Path(runner.__file__).parent / "RunGauntlet.cmd").read_text("utf-8")
    launches = [ln for ln in cmd.splitlines() if "run_sharded_gauntlet.py" in ln
                and not ln.lstrip().lower().startswith("rem")]
    assert launches and all(ln.rstrip().endswith("run_sharded_gauntlet.py %*") for ln in launches)


def test_the_cmd_s_arguments_reach_the_gauntlet_invocation(monkeypatch) -> None:
    import types
    seen: dict[str, object] = {}

    def cli_main() -> int:
        seen["argv"] = list(sys.argv)
        return 0

    fake = types.SimpleNamespace(SHARD_PROTOCOL=2, _cli_main=cli_main,
                                 run_sharded=lambda *a, **k: pytest.fail("sharded a repro run"))
    monkeypatch.setitem(sys.modules, "scripts.external_gauntlet", fake)
    import scripts
    monkeypatch.setattr(scripts, "external_gauntlet", fake, raising=False)
    import research.judging_throughput as jt
    monkeypatch.setattr(jt, "apply_env", lambda *a, **k: None)
    before = list(sys.argv)
    rc = runner.main(["--only", "EURUSD.fam.{}", "--report-to", "r.json"])
    assert rc == 0
    argv = seen["argv"]
    assert isinstance(argv, list)
    assert argv[0].endswith("external_gauntlet.py")
    assert argv[1:] == ["--only", "EURUSD.fam.{}", "--report-to", "r.json"]
    assert sys.argv == before                         # restored for the caller


def test_no_arguments_still_runs_the_sharded_sweep(monkeypatch) -> None:
    import types
    calls: list[int] = []
    fake = types.SimpleNamespace(
        SHARD_PROTOCOL=2, _cli_main=lambda: pytest.fail("no args must not take the CLI path"),
        run_sharded=lambda n, d: calls.append(n) or 0)
    monkeypatch.setitem(sys.modules, "scripts.external_gauntlet", fake)
    import scripts
    monkeypatch.setattr(scripts, "external_gauntlet", fake, raising=False)
    import research.judging_throughput as jt
    monkeypatch.setattr(jt, "apply_env", lambda *a, **k: None)
    monkeypatch.setattr(runner, "DESK", Path(runner.MODEL_FILE).parent)
    monkeypatch.setattr(runner, "decide", lambda *a, **k: {
        "n_shards": 3, "shards_why": "t", "max_concurrency": 1})
    assert runner.main([]) == 0 and calls == [3]


# ------------------------------------------------- M3: out of memory ALONE, and 8 GB cold start
class _FakeJudge:
    """The sealed judge's shard-file helpers, as the patched judge defines them."""

    SHARD_PROTOCOL = 2

    @staticmethod
    def _unpickle(path):
        with open(path, "rb") as fh:
            return pickle.load(fh)  # noqa: S301 - the test's own file

    @staticmethod
    def _pickle_atomic(path, obj):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(obj, fh)

    @staticmethod
    def _mark_done(shard_dir, k, token, phase, cut=None):
        (Path(shard_dir) / f"shard_{k}.done.json").write_text(
            json.dumps({"token": token, "k": k, "phase": phase, "cut": str(cut)}), "utf-8")

    @staticmethod
    def stage0_new_summary():
        return {"rejected": 0}

    @staticmethod
    def _spec_ident(sp):
        return f"{sp['sym']}.{sp['family']}"


def _epoch_dir(tmp_path, n: int = 2, cells: int = 8) -> Path:
    sd = tmp_path / "sd"
    sd.mkdir()
    _FakeJudge._pickle_atomic(sd / "plan.pkl", {"protocol": 2, "token": "tok", "n": n,
                                                "specs": None, "build_t0": 0.0, "meta": {}})
    for k in range(n):
        _FakeJudge._pickle_atomic(sd / f"plan_{k}.pkl",
                                  [(k * 100 + i, {"sym": f"S{k}{i}", "family": "carry"})
                                   for i in range(cells)])
    return sd


def _worker(oom_over: int, always_oom: set[int] | None = None):
    """A fake child that behaves like the sealed `shard_worker` build phase: it reads its plan
    slice from the directory in argv and writes `shard_<k>.pkl`; a slice of more than
    `oom_over` cells (or any slice holding a cell in `always_oom`) dies of memory."""
    launches: list[tuple[int, int]] = []

    def fake(argv, env):
        d, k = Path(argv[-3]), int(argv[-2])
        mine = _FakeJudge._unpickle(d / f"plan_{k}.pkl")
        launches.append((k, len(mine)))
        if len(mine) > oom_over or any(i in (always_oom or set()) for i, _ in mine):
            return 1, 9000.0, {"oom": True}
        _FakeJudge._pickle_atomic(d / f"shard_{k}.pkl", {
            "protocol": 2, "token": "tok", "k": k, "n": 2, "phase": "build",
            "rows": [{"idx": i, "kind": "cell", "obj": sp} for i, sp in mine],
            "built_syms": [sp["sym"] for _i, sp in mine], "dates": [], "build_seconds": 1.0,
            "build_peak_rss_mb": 100.0})
        return 0, 500.0, {"oom": False}
    fake.launches = launches  # type: ignore[attr-defined]
    return fake


def test_an_oom_alone_is_named_and_the_shard_is_recut_not_repeated(tmp_path, monkeypatch):
    """M3: a shard that dies of memory with nothing beside it used to be retried at the same cut
    for the epoch's 24 h life. It is now recorded BLOCKED_SHARD_OOM and re-cut; the parts are
    joined into the one `shard_<k>.pkl` the sealed merge reads."""
    monkeypatch.setattr(runner, "_judge", lambda: _FakeJudge)
    sd = _epoch_dir(tmp_path)
    fake = _worker(oom_over=2)
    runner.RUN.update(run_id="r", planned_cells=16)
    adm = runner.Admission(_model_with(1.0), measure=lambda: 100_000.0, reserve=0.0)
    runner.dispatch(sd, 2, "build", ks=[0], runner=fake, admission=adm)
    out = _FakeJudge._unpickle(sd / "shard_0.pkl")
    assert [r["idx"] for r in out["rows"]] == list(range(8))           # every cell, in order
    assert all(r["kind"] == "cell" for r in out["rows"])
    assert out["token"] == "tok"  # noqa: S105 - the epoch token, not a secret
    assert json.loads((sd / "shard_0.done.json").read_text("utf-8"))["phase"] == "build"
    blocked = json.loads(runner.BLOCKED_FILE.read_text("utf-8"))
    assert blocked["latest"]["action"] == "SPLIT" and blocked["latest"]["k"] == 0
    assert blocked["latest"]["cause"] == "oom_alone" and blocked["latest"]["parts_run"] >= 4
    # the whole-shard cut ran twice (wave + one serial retry), never a third time
    assert sum(1 for k, n in fake.launches if n == 8) == 2
    assert not list(sd.glob("split_*"))


def test_a_cell_that_dies_alone_is_deferred_never_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_judge", lambda: _FakeJudge)
    sd = _epoch_dir(tmp_path)
    runner.RUN.update(run_id="r", planned_cells=16)
    adm = runner.Admission(_model_with(1.0), measure=lambda: 100_000.0, reserve=0.0)
    runner.dispatch(sd, 2, "build", ks=[0], runner=_worker(oom_over=8, always_oom={3}),
                    admission=adm)
    rows = _FakeJudge._unpickle(sd / "shard_0.pkl")["rows"]
    assert [r["idx"] for r in rows] == list(range(8))
    kinds = {r["idx"]: r["kind"] for r in rows}
    assert kinds[3] == "deferred" and sum(k == "cell" for k in kinds.values()) == 7
    assert json.loads(runner.BLOCKED_FILE.read_text("utf-8"))["latest"]["deferred_cells"] == \
        ["S03.carry"]


def test_8gb_box_with_1gb_free_never_launches_a_child_into_an_oom(tmp_path, monkeypatch):
    """The cold-start profile measured on the build box: 8 GB total, ~1 GB free. The reserve is
    a quarter of the total (2 GB), so 1 GB free admits nothing: no child launches, the shard is
    named BLOCKED and the merge fails closed -- instead of a child exported a 1200 MB budget
    the box did not have."""
    monkeypatch.setattr(runner, "_judge", lambda: _FakeJudge)
    monkeypatch.setattr(runner, "total_mb", lambda: 8192.0)
    monkeypatch.setattr(runner, "free_mb", lambda: 1024.0)
    monkeypatch.setattr(runner, "ADMIT_WAIT_S", 0.05)
    assert runner.reserve_mb() == 2048.0
    sd = _epoch_dir(tmp_path)
    fake = _worker(oom_over=100)
    runner.RUN.update(run_id="r", planned_cells=16)
    adm = runner.Admission({}, measure=runner.free_mb)
    acquire = runner.Admission.acquire
    monkeypatch.setattr(runner.Admission, "acquire",
                        lambda self, need, poll_s=0.01, key=None, wait_s=None:
                        acquire(self, need, 0.01, key))
    with pytest.raises(RuntimeError, match="BLOCKED_SHARD_OOM"):
        runner.dispatch(sd, 2, "build", ks=[0], runner=fake, admission=adm)
    assert fake.launches == []                                   # never launched into an OOM
    latest = json.loads(runner.BLOCKED_FILE.read_text("utf-8"))["latest"]
    assert latest["action"] == "BLOCKED" and latest["cause"] == "not_admitted"
    assert latest["reserve_mb"] == 2048.0 and latest["free_mb"] == 1024.0


def test_8gb_box_admits_once_memory_frees_and_exports_only_what_is_there(tmp_path,
                                                                        monkeypatch):
    """Same box, the measured 1 GB rising to 3.5 GB while the shard waits: it launches then,
    with a child budget no larger than free memory over the reserve."""
    monkeypatch.setattr(runner, "_judge", lambda: _FakeJudge)
    monkeypatch.setattr(runner, "total_mb", lambda: 8192.0)
    polls = {"n": 0}

    def measure() -> float:
        polls["n"] += 1
        return 1024.0 if polls["n"] < 4 else 3584.0
    monkeypatch.setattr(runner, "free_mb", measure)
    sd = _epoch_dir(tmp_path)
    envs: list[dict[str, str]] = []
    fake = _worker(oom_over=100)

    def capture(argv, env):
        envs.append(env)
        return fake(argv, env)
    runner.RUN.update(run_id="r", planned_cells=16)
    adm = runner.Admission({}, measure=runner.free_mb)
    acquire = runner.Admission.acquire
    monkeypatch.setattr(runner.Admission, "acquire",
                        lambda self, need, poll_s=0.01, key=None, wait_s=None:
                        acquire(self, need, 0.01, key, wait_s=5.0))
    runner.dispatch(sd, 2, "build", ks=[0], runner=capture, admission=adm)
    assert len(envs) == 1 and polls["n"] >= 4
    assert int(envs[0]["GAUNTLET_MEMORY_BUDGET_MB"]) <= 3584 - 2048
