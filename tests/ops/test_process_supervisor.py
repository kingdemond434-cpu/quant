"""The box process supervisor (zuck 2026-11-13 17:07Z): allowlisted, identity-checked, non-trading,
graceful then bounded force, inside the existing MT5-ReapGitWriters pass. These run REAL
processes (psutil), so the identity rules are tested on the real thing, not a double."""

from __future__ import annotations

import contextlib
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ps = pytest.importorskip("psutil")
from libs.ops import process_supervisor as sup  # noqa: E402

PY = Path(sys.executable).name.lower()
SLEEP = "import time\nwhile True: time.sleep(1)\n"


def _entry(bound: float = 0.5, root: str = "workflow_gate.ps1") -> sup.Entry:
    m = sup.Member("merge_pipeline_watch.py", bound, (PY,))
    return sup.Entry("Quant-WorkflowGate", "ops", root, (m,))


def _spawn(*args: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, "-c", *args])


def _tree(root: subprocess.Popen[bytes], n: int) -> set[int]:
    for _ in range(100):
        kids = ps.Process(root.pid).children(recursive=True)
        if len(kids) >= n:
            return {root.pid} | {k.pid for k in kids}
        time.sleep(0.1)
    raise AssertionError("tree did not start")


def _nest(tmp: Path, root_name: str) -> subprocess.Popen[bytes]:
    member = "import time\ntime.sleep(3600)\n"
    code = (f"import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',{member!r},"
            f"{str(tmp / 'merge_pipeline_watch.py')!r}])\ntime.sleep(3600)\n")  # fmt: skip
    return _spawn(code, str(tmp / root_name))


def _kill(p: subprocess.Popen[bytes]) -> None:
    for k in [*ps.Process(p.pid).children(recursive=True), ps.Process(p.pid)]:
        with contextlib.suppress(Exception):
            k.kill()
    p.wait(timeout=10)


def test_the_drill_recovers_a_simulated_reporter_hang() -> None:
    res = sup.drill()
    assert res["drill"] == "PASS", res
    assert res["left_alive"] == [] and res["root_untouched"]
    row = res["pass"]["stopped"][0]
    assert row["member"] == "merge_pipeline_watch.py" and row["steps"][0].startswith("ended child")


def test_the_real_allowlist_is_non_trading_and_inside_the_task_limit() -> None:
    assert sup.check_allowlist(sup.ALLOWLIST) == []
    for e in sup.ALLOWLIST:
        assert e.lane in ("ops", "data", "research")
        assert max(m.max_age_s for m in e.members) < 30 * 60  # stopped before the task is killed


@pytest.mark.parametrize("bad", [
    sup.Entry("MT5-FTMO-Executor", "ops", "x.ps1", (sup.Member("ftmo_executor.py", 60),)),
    sup.Entry("MT5-Gateway", "ops", "run_gateway_loop.py", (sup.Member("a.py", 60),)),
    sup.Entry("Quant-X", "money", "x.ps1", (sup.Member("a.py", 60),)),
    sup.Entry("Quant-Y", "ops", "x.ps1", ()),
])  # fmt: skip
def test_a_trading_or_malformed_entry_refuses_the_whole_pass(bad: sup.Entry) -> None:
    rec = sup.supervise(apply=True, entries=(bad,))
    assert rec["status"] == "REFUSED" and rec["examined"] == []


def test_a_member_outside_its_tasks_run_is_never_signalled(tmp_path: Path) -> None:
    lone = _spawn(SLEEP, str(tmp_path / "merge_pipeline_watch.py"))
    try:
        time.sleep(1.0)
        rec = sup.supervise(apply=True, entries=(_entry(),), within=lambda p: p.pid == lone.pid)
        assert rec["stopped"] == [] and lone.poll() is None
        assert "no ancestor runs workflow_gate.ps1" in rec["examined"][0]["why"]
    finally:
        _kill(lone)


def test_a_trading_marker_anywhere_in_the_chain_spares_it(tmp_path: Path) -> None:
    root = _nest(tmp_path, "ftmo_workflow_gate.ps1")
    try:
        ids = _tree(root, 1)
        time.sleep(1.0)
        e = _entry(root="ftmo_workflow_gate.ps1")
        # the entry itself would be refused, so test classify directly on the chain rule
        p = next(ps.Process(i) for i in ids if i != root.pid)
        v = sup.classify(ps, p, (e,), set(), time.time())
        assert v is not None and v.action == "spared" and "trading deny list" in v.why
    finally:
        _kill(root)


def test_a_dry_pass_signals_nothing(tmp_path: Path) -> None:
    root = _nest(tmp_path, "workflow_gate.ps1")
    try:
        ids = _tree(root, 1)
        time.sleep(1.0)
        rec = sup.supervise(apply=False, entries=(_entry(),), within=lambda p: p.pid in ids)
        assert rec["verdict"] == "OVERDUE"
        assert [r["action"] for r in rec["examined"]] == ["would stop"]
        assert all(ps.pid_exists(i) for i in ids)
    finally:
        _kill(root)


def test_within_its_bound_is_spared(tmp_path: Path) -> None:
    root = _nest(tmp_path, "workflow_gate.ps1")
    try:
        ids = _tree(root, 1)
        e = _entry(bound=3600)
        rec = sup.supervise(apply=True, entries=(e,), within=lambda p: p.pid in ids)
        assert rec["verdict"] == "CLEAR" and "within its bound" in rec["examined"][0]["why"]
    finally:
        _kill(root)


def test_a_reused_pid_is_not_the_same_process() -> None:
    me = ps.Process()
    assert sup._same(ps, me.pid, me.create_time()) is not None
    assert sup._same(ps, me.pid, me.create_time() - 5.0) is None


def test_the_supervisor_rides_the_existing_reaper_task() -> None:
    src = (ROOT / "scripts/reap_hung_git_writers.py").read_text(encoding="utf-8")
    assert "supervise(apply=a.apply)" in src and "--drill" in src
    inst = (ROOT / "desks/mt5/scripts/install_reap_git_writers_task.ps1").read_text("utf-8")
    assert "reap_hung_git_writers.py --apply" in inst  # no new task, no new scheduler
