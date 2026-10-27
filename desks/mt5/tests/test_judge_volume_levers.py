"""judge_volume v1.1 (2026-10-27): the operator stop holds and is fenced; a shard wave widens on
live memory.

Neither lever touches the sealed judge: the stop decides only WHETHER the resident starts a
sweep, and admission decides only HOW MANY shards of a wave run at once. The verdict-identity
proof (serial vs fixed vs admitted waves through the real sealed `_run_shards`) is the bundle's
harness; here the launcher's own contracts are pinned.
"""

from __future__ import annotations

import itertools
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
    monkeypatch.delenv("GAUNTLET_SHARD_CONCURRENCY", raising=False)
    monkeypatch.delenv("GAUNTLET_SHARD_ADMISSION", raising=False)
    runner._ABORT.clear()


def _stop(text: str | bytes, age_s: float = 60.0) -> Path:
    p = runner.RESIDENT_STOP
    if isinstance(text, bytes):
        p.write_bytes(text)
    else:
        p.write_text(text, encoding="utf-8")
    t = time.time() - age_s
    os.utime(p, (t, t))
    return p


def _events(tmp_path: Path) -> list[dict]:
    f = tmp_path / "events.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


# ------------------------------------------------------------------------ the operator stop
def test_an_empty_stop_holds_and_the_resident_records_its_age(tmp_path) -> None:
    _stop("")
    calls: list[int] = []
    runner.resident(
        sweep=lambda: calls.append(1) or 0, sleep=lambda s: None, clock=_Clock(), max_sweeps=1
    )
    st = json.loads(runner.RESIDENT_STATE.read_text())
    assert calls == [] and st["status"] == "STOPPED" and "HOLD" in st["why"]
    assert st["stop"]["basis"] == "hold" and st["stop_age_s"] >= 0.0
    assert [e["kind"] for e in _events(tmp_path)] == ["JUDGE_STOP_HONOURED"]


@pytest.mark.parametrize(
    "text", ["", "STOP", "HOLD.", "do not resume", "until=tomorrow", "hold", "until="]
)
def test_every_wording_holds_however_old_the_file(text: str) -> None:
    """The audit's probes: none of these may ever lapse, at any age."""
    _stop(text, age_s=400 * 24 * 3600.0)
    got = runner.resident_stop(now=time.time() + 400 * 24 * 3600.0)
    assert got["stopped"] is True and got["basis"] == "hold"
    assert runner.RESIDENT_STOP.exists()


@pytest.mark.parametrize(
    "raw",
    [
        "hold".encode("utf-16"),  # PowerShell 5.1 Out-File default: UTF-16 LE with BOM
        "hold".encode("utf-16-le"),  # no BOM
        b"\xef\xbb\xbfhold",  # UTF-8 with BOM
        b"\xff\xfe\x00\xd8",  # garbage after a UTF-16 BOM
        b"\x80\x81\x82",  # undecodable bytes
    ],
)
def test_any_encoding_holds(raw: bytes) -> None:
    _stop(raw, age_s=30 * 24 * 3600.0)
    assert runner.resident_stop()["stopped"] is True


def test_an_old_mtime_or_a_clock_jump_never_lapses_a_hold() -> None:
    _stop("", age_s=10 * 365 * 24 * 3600.0)  # a preserved mtime from long ago
    first = runner.resident_stop()
    assert first["stopped"] is True and first["stop_age_s"] < 60.0  # age from first honoured
    jumped = runner.resident_stop(now=time.time() + 30 * 24 * 3600.0)  # clock jumps forward
    assert jumped["stopped"] is True and jumped["stop_age_s"] > 29 * 24 * 3600.0
    back = runner.resident_stop(now=time.time() - 24 * 3600.0)  # and back
    assert back["stopped"] is True and back["stop_age_s"] == 0.0


def test_first_honoured_survives_a_relaunch_and_resets_with_a_new_file() -> None:
    _stop("")
    t0 = time.time()
    a = runner.resident_stop(now=t0)
    b = runner.resident_stop(now=t0 + 3 * 3600.0)  # the next relaunch
    assert a["first_honoured_epoch"] == b["first_honoured_epoch"] and b["stop_age_s"] == 10800.0
    runner.RESIDENT_STOP.unlink()
    assert runner.resident_stop(now=t0 + 4 * 3600.0) == {"stopped": False}
    assert not runner.RESIDENT_STOP.with_name("RESIDENT_STOP.honoured.json").exists()
    _stop("")
    c = runner.resident_stop(now=t0 + 5 * 3600.0)
    assert c["stop_age_s"] == 0.0


@pytest.mark.parametrize(
    "raw",
    [
        b"until=2000-01-01T00:00:00Z",
        "until=2000-01-01T00:00:00+00:00".encode("utf-16"),
        b"\xef\xbb\xbfuntil=2000-01-01T00:00:00",
    ],
)
def test_a_lapsed_timed_stop_is_renamed_logged_and_resumed(raw: bytes, tmp_path) -> None:
    p = _stop(raw)
    got = runner.resident_stop()
    assert got["stopped"] is False and got["expired"] is True and got["basis"] == "until"
    assert not p.exists() and (tmp_path / got["renamed_to"]).exists()
    assert [e["kind"] for e in _events(tmp_path)][-1] == "JUDGE_STOP_LAPSED"


def test_a_future_timed_stop_holds() -> None:
    _stop("until=2999-01-01T00:00:00Z")
    got = runner.resident_stop()
    assert got["stopped"] is True and got["basis"] == "until"


def test_a_failed_rename_keeps_holding(monkeypatch, tmp_path) -> None:
    _stop("until=2000-01-01T00:00:00Z")

    def refuse(src, dst):
        raise PermissionError("held open")

    monkeypatch.setattr(runner.os, "replace", refuse)
    got = runner.resident_stop()
    assert got["stopped"] is True and "HOLDING" in got["why"] and got["rename_failed"]
    assert runner.RESIDENT_STOP.exists()
    assert "JUDGE_STOP_LAPSED" not in [e["kind"] for e in _events(tmp_path)]


def test_the_stop_events_go_to_the_desk_event_log_in_production() -> None:
    from libs.ops import events

    real = runner.DESK / "data" / "RESIDENT_STOP"
    assert real.parent / "events.jsonl" == events.PATH
    assert "JUDGE_STOP_HONOURED" in events.KINDS and "JUDGE_STOP_LAPSED" in events.KINDS


def test_no_file_is_no_stop() -> None:
    assert runner.resident_stop() == {"stopped": False}


def test_the_heartbeat_republishes_the_age(monkeypatch) -> None:
    first = time.time() - 5 * 3600.0
    runner._write_state(
        {"status": "STOPPED", "stop": {"first_honoured_epoch": first}, "stop_age_s": 1.0}
    )
    st = json.loads(runner.RESIDENT_STATE.read_text())
    assert 5 * 3600.0 - 5 <= st["stop_age_s"] <= 5 * 3600.0 + 60


@pytest.mark.parametrize(
    ("hours", "state"),
    [
        (0.5, "PASS"),
        (11.9, "PASS"),
        (12.1, "WARN"),
        (23.9, "WARN"),
        (24.1, "FAIL"),
        (108.0, "FAIL"),
    ],
)
def test_the_fence_warns_at_12h_and_fails_at_24h(hours: float, state: str, tmp_path) -> None:
    from datetime import UTC, datetime, timedelta

    from scripts import check_judge_coverage as cov

    now = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)
    first = (now - timedelta(hours=hours)).isoformat(timespec="seconds")
    res = tmp_path / "JUDGE_RESIDENT.json"
    res.write_text(
        json.dumps(
            {
                "status": "STOPPED",
                "why": "RESIDENT_STOP present",
                "stop": {"first_honoured_utc": first},
                "stop_age_s": 1.0,
            }
        )
    )
    assert cov.judge_stop(now, resident=res)["state"] == state
    hb, stall = tmp_path / "hb.json", tmp_path / "stall.json"
    doc = cov.liveness_fence(require_state=True, now=now, heartbeat=hb, stall=stall, resident=res)
    assert doc["state"] == ("UNMEASURED" if state == "PASS" else state)
    assert doc["verdict"] == {"PASS": "UNMEASURED", "WARN": "PASS", "FAIL": "FAIL"}[state]
    off_box = cov.liveness_fence(
        require_state=False, now=now, heartbeat=hb, stall=stall, resident=res
    )
    assert off_box["verdict"] != "FAIL"


def test_the_fence_passes_a_running_judge_and_names_an_unreadable_record(tmp_path) -> None:
    from scripts import check_judge_coverage as cov

    res = tmp_path / "JUDGE_RESIDENT.json"
    res.write_text(json.dumps({"status": "SWEEPING"}))
    assert cov.judge_stop(resident=res)["state"] == "PASS"
    assert cov.judge_stop(resident=tmp_path / "absent.json")["state"] == "UNMEASURED"


# --------------------------------------------------------------------- live shard admission
def _gate(
    n=15,
    floor=2,
    peak=6000.0,
    avail_start=40_000.0,
    avail=lambda: 40_000.0,
    rss=lambda phase: [],
    logs: Path | None = None,
) -> runner._Admission:
    logs = logs or Path("/nonexistent-logs")
    return runner._Admission(
        n, "build", floor, logs, "inv", peak, avail_start, avail=avail, rss=rss
    )


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
    g = _gate(
        floor=1, peak=20_000.0, logs=logs, avail=lambda: 30_000.0, rss=lambda phase: [10_000.0]
    )
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
    assert runner._admission_for(5, "build", 5, tmp_path, "i") is None  # already full width
    runner.SHARD_PEAKS.unlink()
    assert runner._admission_for(15, "build", 2, tmp_path, "i") is None  # never measured


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
    got = runner._admitted_wave(
        6, lambda k: (time.sleep(0.2), (k, None))[1], _Never(), aborted=lambda: True, poll_s=10.0
    )
    assert [k for k, _ in got] == list(range(6)) and time.monotonic() - t0 < 5.0


def test_dispatch_widens_live_and_still_runs_every_shard_once(monkeypatch, tmp_path) -> None:
    runner.SHARD_PEAKS.write_text(json.dumps({"build": [30_000.0]}))
    monkeypatch.setattr(runner, "_available_mb", lambda: 40_000.0)  # floor 1
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


def test_one_light_first_receipt_never_widens_the_wave(tmp_path) -> None:
    """The audit's MF5 probe: 6 GB historic peak, 64 GB free, one 1 GB receipt."""
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "inv-build-0-attempt-0.peak.json").write_text(json.dumps({"peak_mb": 1000.0}))
    g = _gate(n=15, floor=5, peak=6000.0, avail_start=64_000.0, avail=lambda: 64_000.0, logs=logs)
    assert _widest(g) == 5 and g.last["estimate_basis"] == "historic_peak"
    for k in range(1, 5):  # `floor` receipts: only now does this wave's own peak count
        (logs / f"inv-build-{k}-attempt-0.peak.json").write_text(json.dumps({"peak_mb": 1000.0}))
    assert g.admits(5) is True and g.last["estimate_basis"] == "this_wave_peak_x_margin"


def test_at_most_one_extra_shard_is_admitted_per_poll(tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    for k in range(2):
        (logs / f"inv-build-{k}-attempt-0.peak.json").write_text(json.dumps({"peak_mb": 500.0}))
    g = _gate(n=8, floor=2, peak=6000.0, avail_start=64_000.0, avail=lambda: 64_000.0, logs=logs)
    started: dict[int, float] = {}
    lock = threading.Lock()

    def attempted(k: int):
        with lock:
            started[k] = time.monotonic()
        time.sleep(1.5)
        return k, None

    got = runner._admitted_wave(8, attempted, g, aborted=lambda: False, poll_s=0.15)
    assert [k for k, _ in got] == list(range(8))
    extras = sorted(started[k] for k in range(2, 8))
    gaps = [b - a for a, b in itertools.pairwise(extras)]
    assert gaps and min(gaps) >= 0.14, gaps


# ------------------------------------------------------------------- the serial-wall sampler
def test_the_sampler_counts_the_main_threads_stack_per_phase() -> None:
    phase = ["merge_and_publish"]
    ticks = iter(
        [
            {"cpu_s": 10.0, "page_faults": 100.0, "rss_mb": 500.0},
            {"cpu_s": 11.0, "page_faults": 160.0, "rss_mb": 900.0},
            {"cpu_s": 11.5, "page_faults": 170.0, "rss_mb": 700.0},
            {"cpu_s": 20.0, "page_faults": 170.0, "rss_mb": 700.0},
        ]
    )
    s = runner.WallSampler(
        every_s=10.0,
        thread_id=threading.get_ident(),
        phase=lambda: phase[0],
        counters=lambda: next(ticks),
    )
    s.sample()
    s.sample()
    s.sample()
    phase[0] = "done"
    s.sample()  # a new phase never charges the old one's delta
    snap = s.snapshot()
    merge = snap["phases"]["merge_and_publish"]
    assert merge["samples"] == 3 and snap["authority"] == "report_only"
    assert "test_the_sampler_counts_the_main_threads_stack_per_phase" in merge["top"][0]["stack"]
    assert merge["process"]["cpu_s"] == 1.5 and merge["process"]["page_faults"] == 70.0
    assert merge["process"]["sampled_s"] == 20.0 and merge["process"]["cpu_share_of_wall"] == 0.075
    assert merge["process"]["rss_mb_max"] == 900.0
    assert (
        snap["phases"]["done"]["samples"] == 1 and "cpu_s" not in snap["phases"]["done"]["process"]
    )


def test_the_sampler_publishes_into_the_phase_document_only_while_a_sweep_runs() -> None:
    s = runner.WallSampler(
        thread_id=threading.get_ident(), phase=lambda: "plan", counters=lambda: None
    )
    s.sample()
    s.publish()  # no sweep phase open: nothing is written
    assert not runner.SWEEP_PHASE.exists()
    runner._phase("plan")
    s.publish()
    doc = json.loads(runner.SWEEP_PHASE.read_text())
    assert doc["phase"] == "plan" and doc["wall_profile"]["phases"]["plan"]["samples"] == 1


def test_a_sampler_that_cannot_read_anything_records_nothing_and_never_raises() -> None:
    s = runner.WallSampler(thread_id=None, phase=lambda: None, counters=lambda: None)
    s.sample()
    assert s.snapshot()["phases"] == {}
    s2 = runner.WallSampler(thread_id=-1, phase=lambda: "plan", counters=lambda: None)
    s2.sample()
    assert s2.snapshot()["phases"]["plan"]["top"][0]["stack"] == "<main thread not running>"
