"""A warm worker exits when its parent is gone: a parent terminated from outside never runs the
hard stop that reaps its children, and on Windows an orphaned pool worker otherwise waits on its
call queue for ever (Desk health 2026-11-04: one resident at 4.1 GB for ~57h)."""
from __future__ import annotations

import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "scripts"), str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import warm_gauntlet_cache as W  # noqa: E402

psutil = pytest.importorskip("psutil")


def test_a_live_parent_is_present_and_a_dead_or_reused_pid_is_gone(monkeypatch) -> None:
    me = psutil.Process()
    assert W._parent_gone(me.ppid(), me.create_time()) is False
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: False)
    assert W._parent_gone(12345, None) is True
    monkeypatch.undo()
    # a pid that now names a process created AFTER this one is a reused pid: the parent is gone
    assert W._parent_gone(me.pid, me.create_time() - 100.0) is True


def test_an_unreadable_process_table_never_kills_the_worker(monkeypatch) -> None:
    def boom(pid):
        raise PermissionError("access denied")
    monkeypatch.setattr(psutil, "pid_exists", boom)
    assert W._parent_gone(1, 0.0) is False


def test_the_worker_exits_once_its_parent_is_terminated(tmp_path: Path) -> None:
    child = textwrap.dedent(f"""
        import sys, time
        sys.path[:0] = {[str(DESK / "scripts"), str(DESK / "research"), str(DESK),
                         str(DESK.parents[1])]!r}
        import warm_gauntlet_cache as W
        W._watch_parent(0.2)
        time.sleep(60)
    """)
    parent = textwrap.dedent(f"""
        import subprocess, sys, time
        p = subprocess.Popen([sys.executable, "-c", {child!r}])
        print(p.pid, flush=True)
        time.sleep(600)
    """)
    par = subprocess.Popen([sys.executable, "-c", parent], stdout=subprocess.PIPE, text=True)
    try:
        kid = int(par.stdout.readline())
        time.sleep(3.0)                       # the child has imported and armed its watch
        assert psutil.pid_exists(kid)
        par.kill()                            # terminated from outside: no hard stop runs
        par.wait(10)
        deadline = time.time() + 30
        while time.time() < deadline and psutil.pid_exists(kid):
            try:
                if psutil.Process(kid).status() == psutil.STATUS_ZOMBIE:
                    break
            except psutil.NoSuchProcess:
                break
            time.sleep(0.2)
        alive = psutil.pid_exists(kid) and psutil.Process(kid).status() != psutil.STATUS_ZOMBIE
        assert not alive
    finally:
        par.kill()
        par.wait(10)
        if par.stdout is not None:
            par.stdout.close()


def test_the_hard_stop_terminates_rather_than_runs_dll_detach_on_windows(monkeypatch) -> None:
    """pid 36780 (2026-11-02) printed its HARD_STOP END line and stayed resident 2.5 days:
    `os._exit` ends in ExitProcess, whose DLL detach can wait on a lock the killed main thread
    held. On Windows the exit is TerminateProcess; os._exit only if that call fails."""
    import ctypes
    calls: list[tuple[str, int]] = []

    class K32:
        def GetCurrentProcess(self) -> int:
            return -1

        def TerminateProcess(self, handle: int, rc: int) -> int:
            calls.append(("terminate", rc))
            return 1

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"kernel32": K32()})(), raising=False)
    monkeypatch.setattr(W.sys, "platform", "win32")
    monkeypatch.setattr(W.os, "_exit", lambda rc: calls.append(("_exit", rc)))
    W._terminate_self(3)
    assert calls[0] == ("terminate", 3)
    calls.clear()
    monkeypatch.setattr(W.sys, "platform", "linux")
    W._terminate_self(3)
    assert calls == [("_exit", 3)]


def test_the_boot_line_is_flushed_before_anything_heavy_loads() -> None:
    import inspect
    src = inspect.getsource(W._cli_main)
    assert src.index("CacheWarm BOOT") < src.index("_apply_blas_switch()")
    assert src.index("CacheWarm BOOT") < src.index("job_lock")
    assert "_terminate_self(rc)" in inspect.getsource(W._hard_stop)
