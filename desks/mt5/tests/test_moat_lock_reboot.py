"""The moat recorder's PID lock is taken over when the live pid is provably someone else.

After a reboot the recorded pid is often reused by an unrelated process; "a process with that pid
is alive" then kept the recorder standing down until a person deleted the lock (2026-11-17).
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_recorder() -> types.ModuleType:
    """Import the recorder over a TEMPORARY MetaTrader5 stub, then take the stub back out.

    A stub left in sys.modules makes every later `find_spec("MetaTrader5")` raise and every
    importorskip("MetaTrader5") in the suite run against a module with nothing in it.
    """
    had = "MetaTrader5" in sys.modules
    if not had:
        sys.modules["MetaTrader5"] = types.ModuleType("MetaTrader5")
    try:
        from moat import moat_recorder
        return moat_recorder
    finally:
        if not had:
            sys.modules.pop("MetaTrader5", None)


mr = _load_recorder()


def test_same_start_time_is_the_holder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_proc_started", lambda pid: 1000.0)
    assert mr._holder_is_a_stranger({"pid": 7, "proc_started": 1000.4}, 7) is False


def test_a_reused_pid_is_a_stranger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_proc_started", lambda pid: 5000.0)
    assert mr._holder_is_a_stranger({"pid": 7, "proc_started": 1000.0}, 7) is True


def test_unreadable_start_time_is_never_a_takeover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mr, "_proc_started", lambda pid: None)
    assert mr._holder_is_a_stranger({"pid": 7, "proc_started": 1000.0}, 7) is False


def test_an_old_format_lock_from_before_this_boot_is_a_stranger(
        monkeypatch: pytest.MonkeyPatch) -> None:
    boot = datetime(2026, 11, 16, 18, 0, tzinfo=UTC).timestamp()
    monkeypatch.setattr(mr, "_boot_time", lambda: boot)
    before = {"pid": 7, "started": "2026-11-16T12:00:00+00:00"}
    after = {"pid": 7, "started": "2026-11-16T19:00:00+00:00"}
    assert mr._holder_is_a_stranger(before, 7) is True
    assert mr._holder_is_a_stranger(after, 7) is False
    monkeypatch.setattr(mr, "_boot_time", lambda: None)
    assert mr._holder_is_a_stranger(before, 7) is False      # unprovable: stays alive
    assert mr._holder_is_a_stranger({"pid": 7}, 7) is False


def test_the_lock_records_its_own_start_and_the_check_runs_before_refusal() -> None:
    src = (Path(mr.__file__)).read_text(encoding="utf-8")
    body = src[src.index("def single_instance"):]
    assert '"proc_started": _proc_started(os.getpid())' in body
    assert body.index("_holder_is_a_stranger(info, pid)") < body.index("if pid and not stale:")
