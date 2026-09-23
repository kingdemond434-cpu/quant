"""The tree-killing runner and the orphan reaper (libs/ops/proctree.py)."""
from __future__ import annotations

import subprocess
import sys
import time

import pytest

from libs.ops import proctree

psutil = pytest.importorskip("psutil")

GRANDCHILD = (
    "import subprocess, sys, time\n"
    "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "print(p.pid, flush=True)\n"
    "time.sleep(60)\n"
)


def _alive(pid: int) -> bool:
    try:
        pr = psutil.Process(pid)
        return bool(pr.is_running() and pr.status() != psutil.STATUS_ZOMBIE)
    except psutil.NoSuchProcess:
        return False


def test_a_timeout_kills_the_grandchild_too_and_still_raises() -> None:
    with pytest.raises(subprocess.TimeoutExpired) as exc:
        proctree.run([sys.executable, "-u", "-c", GRANDCHILD], timeout=3, capture_output=True,
                     text=True)
    out = exc.value.output or ""
    grand = int(out.strip().splitlines()[0])
    deadline = time.monotonic() + 10
    while _alive(grand) and time.monotonic() < deadline:
        time.sleep(0.2)
    assert not _alive(grand), "the grandchild survived the timeout: the pool leak is back"


def test_a_completed_child_returns_a_completed_process_like_subprocess_run() -> None:
    r = proctree.run([sys.executable, "-c", "print('hi')"], timeout=30, capture_output=True,
                     text=True)
    assert r.returncode == 0 and r.stdout.strip() == "hi" and r.args[0] == sys.executable


def test_check_raises_like_subprocess_run() -> None:
    with pytest.raises(subprocess.CalledProcessError):
        proctree.run([sys.executable, "-c", "raise SystemExit(3)"], timeout=30, check=True)


def _table() -> list[proctree.ProcInfo]:
    P = proctree.ProcInfo
    W = "python -c from multiprocessing.spawn import spawn_main; spawn_main(...)"
    return [
        P(1, 0, "wininit"),
        P(100, 1, "python hourly_cycle.py"),
        P(101, 100, W, 2100),
        P(102, 100, W, 2100),
        P(201, 999, W, 2200),
        P(202, 999, W, 2200),
        P(300, 998, "python gateway_resident.py", 1400),
    ]


def test_only_workers_with_a_dead_parent_are_orphans() -> None:
    orphans = proctree.find_orphaned_workers(_table())
    assert sorted(o.pid for o in orphans) == [201, 202]


def test_the_reaper_kills_orphans_only_and_reports_the_commit_they_held() -> None:
    killed: list[int] = []

    def _kill(pid: int) -> dict[str, int]:
        killed.append(pid)
        return {"killed": 1}

    rep = proctree.reap_orphaned_workers(apply=True, table=_table(), killer=_kill)
    assert killed == [201, 202]
    assert rep["orphans"] == 2 and rep["killed"] == 2 and rep["orphan_commit_mb"] == 4400
    assert rep["workers_total"] == 4 and rep["measured"] is True
    assert rep["orphans_by_dead_parent"] == {"999": {"n": 2, "commit_mb": 4400}}


def test_a_dry_run_counts_and_kills_nothing() -> None:
    killed: list[int] = []
    rep = proctree.reap_orphaned_workers(apply=False, table=_table(),
                                         killer=lambda pid: killed.append(pid))
    assert killed == [] and rep["orphans"] == 2 and rep["killed"] == 0 and rep["applied"] is False


def test_the_desk_actuators_run_the_reaper_first() -> None:
    from libs.ops.control_plane import actuators as ac
    table = ac.desk_actuators()
    assert "reap_orphans" in table
    assert table["reap_orphans"].argv[-1].endswith("reap_orphaned_workers.py")
    import importlib
    sys.path.insert(0, str(ac.DESK / "research"))
    cf = importlib.import_module("clock_fixer")
    assert cf.STEPS[0][0] == "reap_orphans", "commit is freed before any healer runs"
