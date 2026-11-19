"""THE JUDGE RESIDENT REPAIR (2026-11-19): a resident whose heartbeat is stale past 10 minutes is
ended and re-run; the operator stop and a STOPPED resident are healthy; an unreadable heartbeat
acts on nothing; attempts are rate limited and their postcondition is read on the next run.

schtasks is always injected: no test reaches the scheduler or a real process."""
from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 19, 20, 0, tzinfo=UTC)


@pytest.fixture
def jrr() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "judge_resident_repair_t", REPO / "desks/mt5/scripts/judge_resident_repair.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Runner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> int:
        self.calls.append(args)
        return 0


def _resident(tmp: Path, *, age_s: float, status: str = "SWEEPING", pid: int = 111) -> Path:
    p = tmp / "JUDGE_RESIDENT.json"
    p.write_text(json.dumps({"status": status, "pid": pid,
                             "heartbeat_utc": (NOW - timedelta(seconds=age_s)).isoformat()}))
    return p


class Tree:
    """Injected process probe: liveness as the writer, and (cpu_s, io_bytes) per read."""

    def __init__(self, alive: bool | None = True,
                 reads: list[tuple[float, float] | None] | None = None) -> None:
        self.alive = alive
        self.reads = list(reads if reads is not None else [(100.0, 1e6), (100.0, 1e6)])

    def alive_as(self, pid: object, started: object) -> bool | None:
        return self.alive

    def tree(self, pid: int) -> tuple[float, float] | None:
        return self.reads.pop(0) if self.reads else self.reads_last

    reads_last: tuple[float, float] | None = (100.0, 1e6)


def _run(jrr: ModuleType, tmp: Path, resident: Path, runner: Runner, *,
         now: datetime = NOW, on_box: bool = True, probe: Tree | None = None) -> dict:
    pr = probe or Tree()
    return jrr.run(now=now, on_box=on_box, runner=runner, resident=resident,
                   stop=tmp / "RESIDENT_STOP", out=tmp / "out.json", state=tmp / "state.json",
                   sweep=tmp / "GAUNTLET_HEARTBEAT.json", alive_as=pr.alive_as, tree=pr.tree,
                   sleep=lambda s: None, sample_s=10.0)


def test_a_stale_heartbeat_on_an_idle_tree_ends_then_runs_the_task(
        jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=601), r)
    assert doc["reading"]["verdict"] == "WEDGED"
    assert r.calls == [["/End", "/TN", "MT5-Gauntlet"], ["/Run", "/TN", "MT5-Gauntlet"]]
    assert json.loads((tmp_path / "out.json").read_text())["action"]["taken"] is True


def test_a_fresh_heartbeat_on_a_long_sweep_is_left_alone(jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=599), r)
    assert doc["reading"]["verdict"] == "HEALTHY" and r.calls == []


@pytest.mark.parametrize("how", ["stop_file", "status"])
def test_the_operator_stop_is_healthy_and_never_restarted(jrr: ModuleType, tmp_path: Path,
                                                          how: str) -> None:
    r = Runner()
    if how == "stop_file":
        (tmp_path / "RESIDENT_STOP").write_text("hold")
        res = _resident(tmp_path, age_s=99_999)
    else:
        res = _resident(tmp_path, age_s=99_999, status="STOPPED")
    doc = _run(jrr, tmp_path, res, r)
    assert doc["reading"]["verdict"] == "HELD" and r.calls == []


@pytest.mark.parametrize("body", [None, "not json", json.dumps({"status": "SWEEPING"})])
def test_an_unreadable_heartbeat_is_unmeasured_and_acts_on_nothing(
        jrr: ModuleType, tmp_path: Path, body: str | None) -> None:
    res = tmp_path / "JUDGE_RESIDENT.json"
    if body is not None:
        res.write_text(body)
    r = Runner()
    doc = _run(jrr, tmp_path, res, r)
    assert doc["reading"]["verdict"] == "UNMEASURED" and r.calls == []


def test_off_the_box_nothing_is_ended(jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=99_999), r, on_box=False)
    assert doc["reading"]["verdict"] == "STALE" and r.calls == []
    assert not (tmp_path / "state.json").exists()


def test_attempts_are_rate_limited_and_the_postcondition_is_read(
        jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    _run(jrr, tmp_path, _resident(tmp_path, age_s=900, pid=111), r)
    assert len(r.calls) == 2
    # five minutes later still stale: no second attempt inside the hour
    later = NOW + timedelta(minutes=5)
    _run(jrr, tmp_path, _resident(tmp_path, age_s=900 + 300, pid=111), r, now=later)
    assert len(r.calls) == 2
    # a new pid beating after the attempt confirms the repair
    res = tmp_path / "JUDGE_RESIDENT.json"
    res.write_text(json.dumps({"status": "RUNNING", "pid": 222,
                               "heartbeat_utc": (later - timedelta(seconds=10)).isoformat()}))
    _run(jrr, tmp_path, res, r, now=later)
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["last_attempt"]["outcome"] == "CONFIRMED" and st["consecutive_failed"] == 0


def test_a_restart_that_never_beats_is_failed_and_retried_after_the_hour(
        jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    _run(jrr, tmp_path, _resident(tmp_path, age_s=900), r)
    hour = NOW + timedelta(seconds=jrr.REPAIR_MIN_INTERVAL_S + 1)
    _run(jrr, tmp_path, _resident(tmp_path, age_s=900 + 3601), r, now=hour)
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["consecutive_failed"] == 1 and st["attempts"] == 2 and len(r.calls) == 4


def test_box_heartbeat_runs_the_repair_before_the_pager() -> None:
    src = (REPO / "desks/mt5/scripts/box_heartbeat.py").read_text("utf-8")
    body = src[src.index("def main("):]
    assert body.index("_resident_repair()") < body.index("_judge_stall()")


def test_a_stale_heartbeat_on_a_busy_tree_only_pages(jrr: ModuleType, tmp_path: Path) -> None:
    """The HOLD's case: the heartbeat thread died of a non-RuntimeError while the sweep judges."""
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=5_000), r,
               probe=Tree(reads=[(100.0, 0.0), (180.0, 0.0)]))   # 8 cores over 10 s
    assert doc["reading"]["verdict"] == "BUSY" and r.calls == []


def test_a_stale_heartbeat_with_busy_io_only_pages(jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=5_000), r,
               probe=Tree(reads=[(100.0, 0.0), (100.0, 5e7)]))
    assert doc["reading"]["verdict"] == "BUSY" and r.calls == []


def test_a_fresh_sweep_beat_vetoes_the_end(jrr: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "GAUNTLET_HEARTBEAT.json").write_text(json.dumps(
        {"status": "RUNNING", "beat_utc": (NOW - timedelta(seconds=30)).isoformat()}))
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=5_000), r, probe=Tree(alive=False))
    assert doc["reading"]["verdict"] == "BUSY" and r.calls == []


def test_a_stale_sweep_beat_does_not_veto(jrr: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "GAUNTLET_HEARTBEAT.json").write_text(json.dumps(
        {"status": "RUNNING", "beat_utc": (NOW - timedelta(seconds=5_000)).isoformat()}))
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=5_000), r)
    assert doc["reading"]["verdict"] == "WEDGED" and len(r.calls) == 2


def test_a_resident_pid_that_is_not_the_writer_is_wedged(jrr: ModuleType, tmp_path: Path) -> None:
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=5_000), r,
               probe=Tree(alive=False, reads=[]))
    sig = doc["reading"]["second_signal"]
    assert doc["reading"]["verdict"] == "WEDGED" and sig["signal"] == "pid_not_writer"
    assert len(r.calls) == 2


@pytest.mark.parametrize("probe", [Tree(alive=None), Tree(reads=[None, None]),
                                   Tree(reads=[(1.0, 1.0), None])])
def test_an_unmeasurable_second_signal_only_pages(jrr: ModuleType, tmp_path: Path,
                                                  probe: Tree) -> None:
    probe.reads_last = None
    r = Runner()
    doc = _run(jrr, tmp_path, _resident(tmp_path, age_s=5_000), r, probe=probe)
    assert doc["reading"]["verdict"] == "UNMEASURED" and r.calls == []
