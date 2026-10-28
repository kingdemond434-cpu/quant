"""The cache warmer always makes progress, always finishes, and never outranks a miner.

Box read 2026-10-28 (reports/judge/CACHEWARM_STALL_2026-10-28.md): rounds of 12, 11, 2 and 2
cells in 5,465 s .. 90,255 s, each "STOPPED: run budget spent", a log silent after a docket
header, and an hourly trigger that wrote nothing. These pin each repair:

* the docket memo returns the SAME eligible list, order and census as the sealed derivation, and
  a memo hit never re-runs the sealed partition;
* the memo resets when its inputs move or it ages out;
* per-worker memory is sized on measured worker peaks, never the unmeasured 900MB;
* the budget binds the serial phases (nothing is submitted once it is spent) and a drain is
  capped (a hung batch cannot hold a round open);
* the watchdog hard-stops a run stuck in any phase, with a completion line and a report;
* the parent and workers use IDLE or BELOW_NORMAL only -- never anything above the miners.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace

import pytest

DESK = Path(__file__).resolve().parents[1]
for path in (DESK, DESK / "scripts", DESK / "research"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
import judge_docket_order as O  # noqa: E402
import judging_burndown as JB  # noqa: E402
import warm_gauntlet_cache as W  # noqa: E402

from research import job_lock  # noqa: E402


# --------------------------------------------------------------------------- the docket memo
def _rows(n: int, offset: int = 0) -> list[dict]:
    """A docket where every outcome occurs: eligible, rejected, refused, canonicalised, folded."""
    out = []
    for i in range(offset, offset + n):
        fam = ("bad" if i % 7 == 0 else "reject" if i % 5 == 0 else "carry")
        row = {"symbol": ("eurusd" if i % 3 == 0 else f"S{i % 11}"), "family": fam,
               "params": {"k": i % 97}, "available_time": "t"}
        if i % 4 == 0:
            row["timeframe"] = "M15"
        out.append(row)
    out.append(dict(out[0]))          # a duplicate row: first-row-wins
    return out


class _FakeG(SimpleNamespace):
    calls = 0


def _fake_g(tmp_path: Path, rows: list[dict]) -> _FakeG:
    (tmp_path / "external_survivors.json").write_text(json.dumps(rows), encoding="utf-8")

    def partition(specs, meta):
        g.calls += len(specs)
        keep, rej = [], []
        for sp in specs:
            sp["sym"] = str(sp["sym"]).upper()          # the sealed canonical rewrite
            (rej if sp["family"] == "reject" else keep).append(sp)
        return keep, rej

    g = _FakeG(HYP=tmp_path, is_stamped=lambda h: bool(h.get("available_time")),
               partition_at_economic_prior=partition,
               modifier_preflight=lambda sp: "refused" if sp["family"] == "bad" else None,
               timeframe_of=lambda p, f="": str((p or {}).get("timeframe") or "H1").upper())
    return g


def _view(specs: list[dict]) -> list[tuple]:
    return [(sp["sym"], sp["family"], json.dumps(sp["params"], sort_keys=True), sp["tf"])
            for sp in specs]


_CORE = ("rows", "stamped", "unstamped", "cells", "eligible", "rejected_at_prior",
         "modifier_refused")


def test_memo_returns_the_sealed_list_order_and_census(tmp_path: Path) -> None:
    rows = _rows(700)
    plain, c0 = O.sealed_docket(_fake_g(tmp_path, rows), {})
    memo: dict = {}
    g1 = _fake_g(tmp_path, rows)
    first, c1 = O.sealed_docket(g1, {}, memo=memo)
    assert _view(first) == _view(plain)
    assert {k: c1[k] for k in _CORE} == {k: c0[k] for k in _CORE}
    assert c1["memo_new"] == c0["cells"] and c1["memo_hits"] == 0
    assert c0["eligible"] and c0["rejected_at_prior"] and c0["modifier_refused"]

    g2 = _fake_g(tmp_path, rows)
    again, c2 = O.sealed_docket(g2, {}, memo=memo)
    assert g2.calls == 0, "a memo hit must not re-run the sealed partition"
    assert _view(again) == _view(plain)
    assert {k: c2[k] for k in _CORE} == {k: c0[k] for k in _CORE}
    assert c2["memo_hits"] == c0["cells"]


def test_memo_decides_only_new_cells_and_tracks_the_current_docket(tmp_path: Path) -> None:
    memo: dict = {}
    O.sealed_docket(_fake_g(tmp_path, _rows(300)), {}, memo=memo)
    grown = _rows(300) + _rows(50, offset=10_000)
    plain, c0 = O.sealed_docket(_fake_g(tmp_path, grown), {})
    g = _fake_g(tmp_path, grown)
    out, c = O.sealed_docket(g, {}, memo=memo)
    assert _view(out) == _view(plain)
    assert {k: c[k] for k in _CORE} == {k: c0[k] for k in _CORE}
    assert 0 < g.calls <= 50 and c["memo_new"] == g.calls
    shrunk = _rows(40, offset=10_000)
    O.sealed_docket(_fake_g(tmp_path, shrunk), {}, memo=memo)
    assert len(memo) == 40, "the memo holds exactly the current docket's cells"


def test_memo_resets_when_inputs_move_or_it_ages_out(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    uni = tmp_path / "uni"
    uni.mkdir()
    (uni / "universe.json").write_text("{}", encoding="utf-8")
    (uni / "EURUSD_H1.parquet").write_bytes(b"x")
    monkeypatch.setattr(W, "DOCKET_MEMO", tmp_path / "memo.json")
    g = SimpleNamespace(UNI=uni)
    rows, info = W.load_docket_memo(g)
    assert rows == {} and info["why"] == "no memo yet"
    W.save_docket_memo({"a": "R"}, info)
    rows, info2 = W.load_docket_memo(g)
    assert rows == {"a": "R"} and info2["why"] == "reused"
    (uni / "GBPUSD_M5.parquet").write_bytes(b"x")         # a chart arrived
    rows, info3 = W.load_docket_memo(g)
    assert rows == {} and "inputs changed" in info3["why"]
    W.save_docket_memo({"a": "R"}, info3)
    rows, _ = W.load_docket_memo(g, now=time.time() + W.DOCKET_MEMO_TTL_SEC + 1)
    assert rows == {}, "an aged memo is re-decided"


# --------------------------------------------------------------------------- memory admission
def test_worker_need_is_measured_and_never_the_old_900(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WARM_NEED_MB", raising=False)
    monkeypatch.setattr(W, "WORKER_PEAKS", tmp_path / "peaks.json")
    need, why = W.worker_need_mb()
    assert need == W.DEFAULT_WORKER_NEED_MB == 4500.0 and "default" in why
    W.record_worker_peaks([1800, 2100, 1900, 2050])
    need, why = W.worker_need_mb()
    assert need == 2100.0 and "p75 of 4" in why
    monkeypatch.setenv("WARM_NEED_MB", "3000")
    assert W.worker_need_mb()[0] == 3000.0
    monkeypatch.delenv("WARM_NEED_MB")
    W.record_worker_peaks(list(range(1, 200)))
    doc = json.loads((tmp_path / "peaks.json").read_text("utf-8"))
    assert len(doc["peaks"]) == W.WORKER_PEAK_HISTORY


def test_pool_is_sized_on_the_measured_need(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WARM_NEED_MB", raising=False)
    monkeypatch.delenv("WARM_WORKERS", raising=False)
    monkeypatch.delenv("WARM_WORKERS_MAX", raising=False)
    monkeypatch.setattr(W, "WORKER_PEAKS", tmp_path / "peaks.json")
    monkeypatch.setattr(job_lock, "free_mb", lambda: 60_000)
    monkeypatch.setattr(W, "_cpu_idle_cores", lambda sample_s=1.0: 0.0)
    cap = W.measure_capacity()
    # 0.5 x 60,000 / 4,500 = 6 workers (the old 900MB figure read 33, then cores - 1)
    assert cap["by_mem"] == 6 and cap["need_mb_per_worker"] == 4500
    assert cap["pool"] == max(W.HISTORIC_FLOOR, min(max(1, (os.cpu_count() or 1) - 1), 6))
    assert cap["inflight"] == W.HISTORIC_FLOOR, "0.0 idle floors at two, it never blocks"


def test_parent_declares_its_measured_need(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_lock, "observed_peaks", lambda name: [])
    assert W.parent_need_mb() == W.DEFAULT_PARENT_NEED_MB
    monkeypatch.setattr(job_lock, "observed_peaks", lambda name: [4400, 4442, 4454, 3000])
    assert W.parent_need_mb() == 4454


# --------------------------------------------------------------------------- the round's clock
def _round_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool_cls) -> list[dict]:
    report = tmp_path / "throughput.json"
    report.write_text(json.dumps({"decision": {"task_time_limit_s": 0}}))
    monkeypatch.setattr(W, "JUDGING_THROUGHPUT", report)
    monkeypatch.setattr(W, "DEFERRALS", tmp_path / "deferrals.json")
    monkeypatch.setattr(W, "WORKER_PEAKS", tmp_path / "peaks.json")
    monkeypatch.setattr(JB, "sweep_anatomy", lambda: {"status": "UNMEASURED"})
    specs = [{"sym": "USDJPY", "tf": "H1", "family": "carry", "params": {}, "ckey": f"k{i}",
              "_never_judged": True} for i in range(6)]
    monkeypatch.setattr(W, "docket_specs", lambda *a: specs)
    monkeypatch.setattr(O, "sealed_keep", lambda *a: (specs, {
        "keep": 6, "keep_never_judged": 6, "outside_keep": 0}))
    monkeypatch.setattr(W, "resolve_keys", lambda *a: (specs, {}, 0))
    monkeypatch.setattr(W, "on_disk_keys", lambda *a: set())
    monkeypatch.setattr(W, "split_deferred", lambda cold, *a: (cold, [], {}))
    monkeypatch.setattr(W, "plan_equivalents", lambda g, keyed, warm, order, held:
                        (order, {}, 0))
    monkeypatch.setattr(W, "measure_capacity", lambda: {
        "pool": 2, "inflight": 2, "cores": 18, "idle_cores": 0.0, "free_mb": 60000})
    monkeypatch.setattr(job_lock, "free_mb", lambda: 60000)
    import concurrent.futures
    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", pool_cls)
    return specs


def test_a_budget_spent_in_the_serial_phases_submits_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class NeverPool:
        def __init__(self, **kwargs):
            raise AssertionError("no pool may open once the budget is spent")

    _round_fixture(tmp_path, monkeypatch, NeverPool)
    r = W.run_round(SimpleNamespace(CACHE_DIR=tmp_path), {}, None, time.time() - 1)
    assert r["warmed"] == 0 and r["cold"] == 6
    assert "before the build phase" in r["stopped"]
    assert set(r["phase_seconds"]) >= {"docket_load", "sealed_order", "keying", "plan"}


def test_a_hung_batch_cannot_hold_the_round_open(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class HungPool:
        def __init__(self, **kwargs):
            pass

        def submit(self, builder, batch):
            f: Future = Future()
            f.set_running_or_notify_cancel()      # running: cancel() cannot take it back
            return f

        def shutdown(self, wait=True, cancel_futures=False):
            closed.append(bool(wait))

        def terminate_workers(self):
            closed.append(False)

    _round_fixture(tmp_path, monkeypatch, HungPool)
    monkeypatch.setattr(W, "DRAIN_SEC", 0.2)
    t0 = time.time()
    r = W.run_round(SimpleNamespace(CACHE_DIR=tmp_path), {}, None, time.time() + 0.1)
    assert time.time() - t0 < 30, "the drain is capped"
    assert r["abandoned_in_flight"] > 0 and r["stopped"].startswith("run budget spent")
    assert closed and closed[0] is False, "workers are terminated, not waited on"


def test_batches_report_their_worker_peak_and_both_shapes_are_read() -> None:
    assert W._batch_outcomes([("k", "warmed")]) == ([("k", "warmed")], None, None)
    out = W._batch_outcomes({"res": [("k", "hit")], "pid": 7, "peak_mb": 2048})
    assert out == ([("k", "hit")], 7, 2048)


# --------------------------------------------------------------------------- the hard stop
def test_a_run_stuck_in_any_phase_ends_with_a_report_and_a_completion_line(
        tmp_path: Path) -> None:
    code = (
        "import sys, time\n"
        f"sys.path[:0] = [{str(DESK)!r}, {str(DESK / 'scripts')!r}, {str(DESK / 'research')!r}]\n"
        "from pathlib import Path\n"
        "import warm_gauntlet_cache as W\n"
        f"W.REPORT = Path({str(tmp_path / 'r.json')!r})\n"
        "W.start_watchdog(time.time())\n"
        "W._STATE['admitted'] = True\n"
        "W._phase('docket_load')\n"
        "time.sleep(60)\n"
        "print('NOT REACHED')\n")
    env = {**os.environ, "WARM_BUDGET_SEC": "1", "WARM_GRACE_SEC": "1",
           "WARM_HEARTBEAT_SEC": "0.5"}
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env=env, timeout=50, check=False)
    assert time.time() - t0 < 45
    assert proc.returncode == W.HARD_STOP_RC == 3, proc.stderr
    assert "NOT REACHED" not in proc.stdout
    assert "CacheWarm END status=HARD_STOP rc=3 phase=docket_load" in proc.stdout
    doc = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert doc["status"] == "HARD_STOP" and doc["phase"] == "docket_load"
    assert doc["in_progress"] is False


def test_a_duplicate_never_clobbers_the_live_report(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """v1.1: a run that was not admitted never writes REPORT at all (lock-then-write raced)."""
    monkeypatch.setattr(W, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(W, "NOT_ADMITTED", tmp_path / "na.json")
    monkeypatch.setattr(W, "DESK", tmp_path)
    (tmp_path / "r.json").write_text(json.dumps({"status": "RUNNING", "rounds": [{"a": 1}]}))
    locks = tmp_path / "data" / ".job_locks"
    locks.mkdir(parents=True)
    (locks / "warm_gauntlet_cache.json").write_text(json.dumps({"pid": 4242}))
    assert W.not_admitted_status().startswith("REFUSED_DUPLICATE")
    (locks / "warm_gauntlet_cache.json").unlink()
    assert W.not_admitted_status() == "NOT_ADMITTED"
    assert json.loads((tmp_path / "r.json").read_text("utf-8"))["status"] == "RUNNING"
    assert json.loads((tmp_path / "na.json").read_text("utf-8"))["status"] == "NOT_ADMITTED"


# --------------------------------------------------------------------------- never above miners
class _FakeProc:
    def __init__(self, sink: list, start: int) -> None:
        self.sink, self.cur = sink, start

    def nice(self, value=None):
        if value is None:
            return self.cur
        self.sink.append(value)
        self.cur = value
        return None


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_priorities_are_idle_or_equal_never_above(monkeypatch: pytest.MonkeyPatch,
                                                  platform: str) -> None:
    sink: list = []
    proc = _FakeProc(sink, 0)
    fake = SimpleNamespace(IDLE_PRIORITY_CLASS=64, BELOW_NORMAL_PRIORITY_CLASS=16384,
                           NORMAL_PRIORITY_CLASS=32, Process=lambda: proc)
    monkeypatch.setitem(sys.modules, "psutil", fake)
    monkeypatch.setattr(sys, "platform", platform)
    W._set_priority(W.EQUAL)
    W._set_priority(W.IDLE)
    W._set_priority("anything else reads as equal")
    if platform == "win32":
        assert sink == [16384, 64, 16384]
    else:
        assert sink == [10, 19], "POSIX only ever raises nice; never below the miners' class"


def test_defaults_parent_equal_workers_idle() -> None:
    assert W.PARENT_PRIORITY == W.EQUAL or os.environ.get("WARM_PARENT_PRIORITY")
    assert W.EQUAL_WORKERS == 0 or os.environ.get("WARM_EQUAL_WORKERS"), (
        "EQUAL-priority workers take CPU share from the miners: opt-in only")


# --------------------------------------------------------------------------- v1.1 (audit 6ea07bdf2)
def test_close_pool_kills_real_hung_workers() -> None:
    """MUST-FIX 1: a REAL ProcessPoolExecutor with hung workers ends with 0 alive."""
    from concurrent.futures import ProcessPoolExecutor

    pool = ProcessPoolExecutor(max_workers=2)
    futs = [pool.submit(time.sleep, 120) for _ in range(2)]
    t_end = time.time() + 30
    while time.time() < t_end and not (all(f.running() for f in futs)
                                       and len(pool._processes or {}) == 2):
        time.sleep(0.1)
    procs = list((pool._processes or {}).values())
    assert len(procs) == 2
    t0 = time.time()
    dead = W._close_pool(pool, kill=True)
    assert time.time() - t0 < 20
    assert dead == 2
    assert not any(pr.is_alive() for pr in procs), "every hung worker is dead"


def test_a_memory_floor_stop_frees_workers_without_a_drain(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class HungPool:
        def __init__(self, **kwargs):
            pass

        def submit(self, builder, batch):
            f: Future = Future()
            f.set_running_or_notify_cancel()
            return f

        def shutdown(self, wait=True, cancel_futures=False):
            closed.append(bool(wait))

    _round_fixture(tmp_path, monkeypatch, HungPool)
    monkeypatch.setattr(job_lock, "free_mb", lambda: 100)
    monkeypatch.setattr(W, "DRAIN_SEC", 600.0)
    t0 = time.time()
    r = W.run_round(SimpleNamespace(CACHE_DIR=tmp_path), {}, None, time.time() + 3600)
    assert time.time() - t0 < 30, "a memory stop does not wait out the drain"
    assert "floor" in r["stopped"] and r["abandoned_in_flight"] > 0
    assert closed == [False], "the pool is killed, never waited on"


def _fresh_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(W, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(W, "_STATE", {"phase": "x", "phase_since": time.time(), "rounds": [],
                                      "status": "RUNNING", "admitted": False})


def test_the_heartbeat_carries_the_previous_rounds(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """MUST-FIX 2: until this run's first round lands, the report keeps the last run's rounds."""
    _fresh_state(monkeypatch, tmp_path)
    (tmp_path / "r.json").write_text(json.dumps({"status": "DONE", "rounds": [
        {"warmed": 1}, {"warmed": 2}, {"warmed": 3}, {"warmed": 4}]}))
    W._load_prev_rounds()
    W._STATE["admitted"] = True
    assert W._publish("RUNNING")
    doc = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert [r["warmed"] for r in doc["rounds"]] == [2, 3, 4]
    assert doc["rounds_source"].startswith("previous run")
    import judging_burndown as JB2
    monkeypatch.setattr(JB2, "WARM", tmp_path / "r.json")
    assert JB2.warm_side()["status"] == "MEASURED"
    W._STATE["rounds"].append({"warmed": 9})
    assert W._publish("RUNNING")
    doc = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert doc["rounds"] == [{"warmed": 9}] and doc["rounds_source"] == "this run"


def test_running_never_lands_after_a_final_status(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    _fresh_state(monkeypatch, tmp_path)
    assert not W._publish("RUNNING"), "an unadmitted run owns no report"
    W._STATE["admitted"] = True
    assert W._publish("RUNNING")
    assert W._publish("DONE")
    assert not W._publish("RUNNING")
    assert not W._publish("HARD_STOP")
    assert json.loads((tmp_path / "r.json").read_text("utf-8"))["status"] == "DONE"
    import threading as th
    _fresh_state(monkeypatch, tmp_path)
    W._STATE["admitted"] = True
    stop = th.Event()

    def beat() -> None:
        while not stop.is_set():
            W._publish("RUNNING")

    ts = [th.Thread(target=beat) for _ in range(4)]
    for t in ts:
        t.start()
    time.sleep(0.05)
    W._publish("DONE")
    time.sleep(0.05)
    stop.set()
    for t in ts:
        t.join()
    assert json.loads((tmp_path / "r.json").read_text("utf-8"))["status"] == "DONE"


def test_a_bad_equal_workers_value_never_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw, want in (("two", 0), ("", 0), ("nan", 0), ("-3", 0), ("2", 2), ("2.9", 2),
                      ("inf", 0)):
        monkeypatch.setenv("WARM_EQUAL_WORKERS", raw)
        assert W._env_count("WARM_EQUAL_WORKERS", 0) == want, raw
    paths = [str(DESK), str(DESK / "scripts"), str(DESK / "research")]
    code = ("import sys\n"
            f"sys.path[:0] = {paths!r}\n"
            "import warm_gauntlet_cache as W\nprint('EQ', W.EQUAL_WORKERS)\n")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env={**os.environ, "WARM_EQUAL_WORKERS": "lots"}, timeout=60,
                          check=False)
    assert proc.returncode == 0 and "EQ 0" in proc.stdout, proc.stderr


def test_the_memo_key_moves_with_the_mechanism(tmp_path: Path) -> None:
    rows = [{"symbol": "EURUSD", "family": "carry", "params": {"k": 1},
             "mechanism_status": "NAMED", "mechanism_note": "a"}]
    memo: dict = {}
    O.sealed_docket(_fake_g(tmp_path, rows), {}, memo=memo)
    rows[0]["mechanism_status"] = "STATISTICAL_ONLY"
    g = _fake_g(tmp_path, rows)
    _out, c = O.sealed_docket(g, {}, memo=memo)
    assert c["memo_new"] == 1 and g.calls == 1, "an edited mechanism is re-decided"
    assert O.memo_key("k", {"mechanism_note": "a"}) != O.memo_key("k", {"mechanism_note": "b"})


def test_live_terminal_outcomes_expire_on_their_own_clock(tmp_path: Path) -> None:
    uni = tmp_path / "uni"
    uni.mkdir()
    (uni / "EURUSD_H1.parquet").write_bytes(b"x")       # H1 present, M15 absent
    rows = [{"symbol": "EURUSD", "family": "carry", "params": {"timeframe": "M15"}},
            {"symbol": "EURUSD", "family": "carry", "params": {}}]
    g = _fake_g(tmp_path, rows)
    g.UNI = uni
    cells = {"a": {"sym": "EURUSD", "family": "carry", "params": {"timeframe": "M15"}},
             "b": {"sym": "EURUSD", "family": "carry", "params": {}}}
    memo: dict = {}
    census = {"rejected_at_prior": 0, "modifier_refused": 0}
    O._partition_memoised(g, {}, cells, memo, dict(census), now=10 * 3600.0)
    marks = sorted(v for v in memo.values())
    assert any(O.LIVE_MARK in v for v in marks) and any(O.LIVE_MARK not in v for v in marks)
    g.calls = 0
    O._partition_memoised(g, {}, cells, memo, dict(census), now=10 * 3600.0 + 60)
    assert g.calls == 0
    O._partition_memoised(g, {}, cells, memo, dict(census), now=12 * 3600.0)
    assert g.calls == 1, "only the live-dependent outcome is re-decided after its TTL"


def test_orphan_tmps_are_swept_only_when_old_and_unowned(tmp_path: Path) -> None:
    now = time.time()
    dead_pid = 4_000_000          # above any real pid range check -> treated as no pid
    files = {"k1.999999.tmp": now - 7200, "k2.999999.fan.tmp": now - 7200,
             f"k3.{os.getpid()}.tmp": now - 7200, "k4.999999.tmp": now - 10,
             "k5.npz": now - 7200, "r.json.999999.140234567890123.tmp": now - 7200,
             f"k6.{dead_pid}.tmp": now - 7200}
    for name, mt in files.items():
        f = tmp_path / name
        f.write_bytes(b"x")
        os.utime(f, (mt, mt))
    import psutil
    if psutil.pid_exists(999999):
        pytest.skip("pid 999999 happens to be alive here")
    out = W.sweep_orphan_tmps([tmp_path], now=now, min_age_s=3600)
    left = sorted(p.name for p in tmp_path.iterdir())
    assert "k5.npz" in left, "never anything but *.tmp"
    assert f"k3.{os.getpid()}.tmp" in left, "never a file a live writer names"
    assert "k4.999999.tmp" in left, "never a young file"
    assert "k1.999999.tmp" not in left and "k2.999999.fan.tmp" not in left
    assert out["removed"] == 4 and out["young"] == 1 and out["live_writer"] == 1
