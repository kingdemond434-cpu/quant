"""ARCH-07: the load drill times the trading path's own decision code under research load (with an
equal-priority control), the separation census fails any research process at or above the trading
side's priority, a host with no trading process is UNMEASURED, and recovery_drills grades both."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import load_isolation_drill as li  # noqa: E402
from research import recovery_drills as rd  # noqa: E402

NOW = datetime(2026, 11, 10, 12, tzinfo=UTC)
NORMAL = 0 if os.name != "nt" else 0x20
LOW = 10 if os.name != "nt" else 0x4000


def _p(pid: int, cmd: str, nice: int) -> dict:
    return {"pid": pid, "name": "python", "cmdline": cmd.split(), "nice": nice}


def test_classify_sides_by_command_line() -> None:
    assert li.classify(["python", r"C:\opt\quant\desks\mt5\research\gateway_resident.py"]) \
        == "trading"
    assert li.classify(["terminal64.exe"]) == "trading"
    assert li.classify(["python", "desks/mt5/research/hourly_cycle.py"]) == "research"
    assert li.classify(["python", "desks/mt5/scripts/external_gauntlet.py"]) == "research"
    assert li.classify(["bash"]) is None
    assert li.classify([]) is None


def test_research_below_trading_passes() -> None:
    doc = li.separation_census([
        _p(11, "python desks/mt5/mt5desk/gateway.py", NORMAL),
        _p(12, "python desks/mt5/research/hourly_cycle.py", LOW),
        _p(13, "python desks/mt5/scripts/external_gauntlet.py", LOW)])
    assert doc["verdict"] == "PASS", doc
    assert doc["research_n"] == 2


def test_research_at_trading_priority_fails_and_names_it() -> None:
    doc = li.separation_census([
        _p(11, "python desks/mt5/research/run_gateway_loop.py", NORMAL),
        _p(12, "python desks/mt5/research/pf_allocator.py", NORMAL)])
    assert doc["verdict"] == "FAIL"
    assert [o["pid"] for o in doc["offenders"]] == [12]


def test_no_trading_process_is_unmeasured_never_pass() -> None:
    doc = li.separation_census([_p(12, "python desks/mt5/research/hourly_cycle.py", LOW)])
    assert doc["verdict"] == "UNMEASURED"
    doc = li.separation_census([_p(11, "python desks/mt5/mt5desk/gateway.py", NORMAL)])
    assert doc["verdict"] == "UNMEASURED"


def test_the_drill_itself_is_not_counted() -> None:
    doc = li.separation_census([
        _p(11, "python desks/mt5/mt5desk/gateway.py", NORMAL),
        _p(os.getpid(), "python desks/mt5/research/load_isolation_drill.py", NORMAL)])
    assert doc["verdict"] == "UNMEASURED"


def test_load_drill_fails_when_the_separated_arm_starves_the_probe(
        monkeypatch: pytest.MonkeyPatch) -> None:
    arms = iter([{"n": 9, "p99_ms": 1.0}, {"n": 9, "p99_ms": 5.0}, {"n": 9, "p99_ms": 4.0}])
    monkeypatch.setattr(li, "_arm", lambda *a, **k: next(arms))
    monkeypatch.setattr(li, "_lower_spawn_kwargs", lambda: {})
    doc = li.load_drill(lambda: None, workers=2)
    assert doc["verdict"] == "FAIL" and doc["separated_p99_ratio"] == 4.0


def test_load_drill_passes_and_reports_its_sensitivity(monkeypatch: pytest.MonkeyPatch) -> None:
    arms = iter([{"n": 9, "p99_ms": 1.0}, {"n": 9, "p99_ms": 3.0}, {"n": 9, "p99_ms": 1.1}])
    monkeypatch.setattr(li, "_arm", lambda *a, **k: next(arms))
    monkeypatch.setattr(li, "_lower_spawn_kwargs", lambda: {})
    doc = li.load_drill(lambda: None, workers=2)
    assert doc["verdict"] == "PASS" and doc["sensitive"] is True


def test_no_lower_class_is_unmeasured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(li, "_arm", lambda *a, **k: {"n": 9, "p99_ms": 1.0})
    monkeypatch.setattr(li, "_lower_spawn_kwargs", lambda: None)
    assert li.load_drill(lambda: None, workers=1)["verdict"] == "UNMEASURED"


def test_real_drill_runs_briefly_against_the_real_decision_code() -> None:
    t0 = time.monotonic()
    doc = li.load_drill(seconds=0.2, workers=1)
    assert doc["verdict"] in ("PASS", "FAIL", "UNMEASURED")
    assert doc["baseline"]["n"] > 0 and doc["equal_priority"]["workers"] == 1
    assert time.monotonic() - t0 < 30


def test_recovery_drills_grades_both_halves(tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "LOAD_ISOLATION.json"
    monkeypatch.setattr(rd, "LOAD", p)
    assert rd._load_part("load", "x", NOW)["verdict"] == "UNMEASURED"
    p.write_text(json.dumps({"generated_utc": NOW.isoformat(),
                             "load": {"verdict": "PASS", "why": "ok"},
                             "separation": {"verdict": "FAIL", "why": "pf_allocator at NORMAL"}}))
    assert rd._load_part("load", "x", NOW)["verdict"] == "PASS"
    sep = rd._load_part("separation", "x", NOW)
    assert sep["verdict"] == "FAIL" and "pf_allocator" in sep["why"]
    ids = {d for d, _, _ in rd.DRILLS}
    assert {"load", "workload_separation"} <= ids
