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


def _run(jrr: ModuleType, tmp: Path, resident: Path, runner: Runner, *,
         now: datetime = NOW, on_box: bool = True) -> dict:
    return jrr.run(now=now, on_box=on_box, runner=runner, resident=resident,
                   stop=tmp / "RESIDENT_STOP", out=tmp / "out.json", state=tmp / "state.json")


def test_a_stale_heartbeat_ends_then_runs_the_task(jrr: ModuleType, tmp_path: Path) -> None:
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
    assert doc["reading"]["verdict"] == "WEDGED" and r.calls == []
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
