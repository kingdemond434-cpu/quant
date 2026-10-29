"""The hourly job_lock_health leg: every held lock's owner is looked at, a WEDGED research owner
is stopped after two hours by command line (never by bare pid), and nothing on the judge,
certifier, terminal lane or money path is ever stopped automatically."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "desks" / "mt5"))
sys.path.insert(0, str(ROOT / "desks" / "mt5" / "research"))

import check_job_locks as C  # noqa: E402
import job_lock as J  # noqa: E402


@pytest.fixture()
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(J, "LOCK_ROOT", tmp_path)
    monkeypatch.setattr(J, "HEALTH_REPORT", tmp_path / "JOB_LOCK_HEALTH.json")
    monkeypatch.setattr(J, "_owner_state", lambda path: "ALIVE")
    return tmp_path


def _hold(root: Path, name: str, pid: int = 18040) -> Path:
    p = root / f"{name}.json"
    p.write_text(json.dumps({"token": f"t-{name}", "pid": pid, "host": socket.gethostname()}),
                 "utf-8")
    return p


def test_a_wedged_research_owner_is_stopped_after_two_hours(root: Path) -> None:
    _hold(root, "merge_hypotheses")
    stops: list[tuple[int, tuple[str, ...]]] = []

    def stop(pid, frags):
        stops.append((pid, frags))
        return {"stopped": True, "why": "terminated"}

    C.run(root=root, now=0.0, stop=stop, cpu_of=lambda pid: 50.0)
    one_h = C.run(root=root, now=3600.0, stop=stop, cpu_of=lambda pid: 50.0)
    assert one_h["status"] == "RED" and one_h["wedged"] == ["merge_hypotheses"] and not stops
    two_h = C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=stop, cpu_of=lambda pid: 50.0)
    assert stops == [(18040, C.AUTO_STOP_JOBS["merge_hypotheses"])]
    assert two_h["locks"]["merge_hypotheses"]["status"] == "STOPPED"
    assert two_h["status"] == "OK"


def test_the_money_path_and_the_judge_are_never_stopped(root: Path) -> None:
    assert not (set(C.AUTO_STOP_JOBS) & C.NEVER_STOP)
    for name in sorted(C.NEVER_STOP):
        _hold(root, name)
    called: list[int] = []
    C.run(root=root, now=0.0, stop=lambda p, f: called.append(p), cpu_of=lambda pid: 1.0)
    out = C.run(root=root, now=10 * C.AUTO_STOP_AFTER_S, stop=lambda p, f: called.append(p),
                cpu_of=lambda pid: 1.0)
    assert not called
    assert out["status"] == "RED" and out["wedged"] == sorted(C.NEVER_STOP)


def test_a_refused_stop_stays_red(root: Path) -> None:
    _hold(root, "merge_hypotheses")
    refuse = lambda pid, f: {"stopped": False, "why": "stop refused: AccessDenied"}  # noqa: E731
    C.run(root=root, now=0.0, stop=refuse, cpu_of=lambda pid: 1.0)
    out = C.run(root=root, now=C.AUTO_STOP_AFTER_S + 60, stop=refuse, cpu_of=lambda pid: 1.0)
    assert out["status"] == "RED"
    assert "AccessDenied" in out["locks"]["merge_hypotheses"]["auto_stop"]["why"]


def test_stop_checks_the_command_line_before_touching_a_pid(monkeypatch) -> None:
    import os
    res = C._stop(os.getpid(), ("definitely_not_this_process_xyz",))
    assert res["stopped"] is False and "pid reused" in res["why"]


def test_sidecars_are_not_locks(root: Path) -> None:
    _hold(root, "edge_search")
    (root / "edge_search.progress.json").write_text("{}", "utf-8")
    (root / "edge_search.peaks.json").write_text("[]", "utf-8")
    assert [p.name for p in C._locks(root)] == ["edge_search.json"]


def test_the_leg_is_hourly_and_its_report_is_watched() -> None:
    hc = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    core = hc[hc.index("CORE_LEGS: frozenset[str] = frozenset({"):]
    assert '"job_lock_health"' in core[: core.index("})")]
    assert '_costed("job_lock_health", job_lock_health)' in hc and '"job_lock_health": jlh' in hc
    sys.path.insert(0, str(ROOT))
    from libs.research import layers
    assert layers.LEG_LAYER.get("job_lock_health") == "meta"
    from research import issue_board as board
    assert any(c[1].endswith("JOB_LOCK_HEALTH.json") for c in board.CADENCE)
