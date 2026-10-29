"""process_health under memory pressure (v5f).

MEASURED 2026-10-21 04:01:35Z on the trading box: all 73 tasks read SCHEDULER_UNMEASURED while
stall_watch showed 1,654 MB free of 8,186 MB and a 37,950 MB commit. These pin what the probe now
does about it: a timeout names the read, its bound and the memory picture (psutil only, stamped
with the host and its total); the longer-bound retry runs DETACHED and below normal priority,
never inline in the pass that overran; and a retry that lands replaces the UNMEASURED report.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "process_health_pressure_under_test", ROOT / "ops" / "process_health.py"
)
assert _spec and _spec.loader
ph = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ph)

BRIEF = (
    '"TaskName","Next Run Time","Status"\r\n'
    '"\\MT5-Hourly","20/10/2026 19:05:00","Ready"\r\n'
)
VERBOSE = (
    '"HostName","TaskName","Next Run Time","Status","Last Run Time","Last Result",'
    '"Scheduled Task State"\r\n'
    '"BOX","\\MT5-Hourly","20/10/2026 19:05:00","Ready","20/10/2026 18:05:00","0","Enabled"\r\n'
)
MEM = {"host": "TEST-BOX-1", "source": "psutil", "at": "2026-10-21T04:01:35+00:00",
       "total_phys_mb": 8186, "free_phys_mb": 1654, "commit_charge_mb": 37950,
       "commit_limit_mb": 40000, "commit_source": "test"}


def _fake(monkeypatch: pytest.MonkeyPatch, answers: dict[int, Any]) -> list[tuple[str, int]]:
    """Answer by BOUND: the same query answers or times out depending on the budget it got."""
    calls: list[tuple[str, int]] = []

    def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
        assert cmd[0] == "schtasks", cmd
        bound = int(kw["timeout"])
        calls.append(("/v" if "/v" in cmd else "brief", bound))
        answer = answers.get(bound)
        if answer is None:
            raise subprocess.TimeoutExpired(cmd, bound)
        return subprocess.CompletedProcess(cmd, 0, answer, "")

    monkeypatch.setattr(ph.subprocess, "run", run)
    return calls


@pytest.fixture
def box(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    (tmp_path / "fresh.json").write_text(
        json.dumps({"generated_at": datetime.now(UTC).isoformat(timespec="seconds")}), "utf-8")
    monkeypatch.setattr(ph, "ROOT", tmp_path)
    # The board's off-scheduler rows (pager, Fusion deadman, disk floor) read the real box;
    # these tests are about the scheduler, so those rows are held clear.
    monkeypatch.setattr(ph, "_alerts_armed", lambda root=None: {"armed": 1, "kinds": ["hc"],
                                                                "line": None})
    monkeypatch.setattr(ph, "deadman_invariant", lambda **kw: None)
    monkeypatch.setattr(ph, "disk_state", lambda *a, **kw: {"verdict": "OK"})
    monkeypatch.setattr(ph, "_realised_risk_row", lambda: None)
    monkeypatch.setattr(ph, "OUT", tmp_path / "reports" / "process_health.json")
    monkeypatch.setattr(ph, "_contracts", lambda: {"MT5-Hourly": ("fresh.json", 120, "hourly")})
    monkeypatch.setattr(ph, "memory_snapshot", lambda: dict(MEM))
    monkeypatch.setattr(ph, "account_key_file", lambda: {"state": "present"})
    monkeypatch.setattr(ph, "account_key_backup", lambda: {"state": "ok"})
    return tmp_path


class _Popen:
    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, cmd: list[str], **kw: Any) -> None:
        _Popen.calls.append({"cmd": list(cmd), **kw})


def test_a_timeout_carries_the_read_the_bound_and_the_memory(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _fake(monkeypatch, {})   # nothing answers at 45 s
    doc = ph.build()
    assert doc["status"] == "UNMEASURED"
    [t] = doc["scheduler_timeouts"]
    assert t["read"] == "schtasks /query /fo csv" and t["bound_s"] == 45
    assert t["memory"]["free_phys_mb"] == 1654
    assert t["memory"]["commit_charge_mb"] == 37950
    # the reason in the headline names the same facts, in words
    st = doc["scheduler_status"]
    assert "schtasks /query /fo csv" in st and "45 s bound" in st
    assert "1,654 MB free of 8,186 MB" in st and "commit 37,950 MB" in st
    assert "TEST-BOX-1" in st


def test_a_verbose_timeout_names_the_verbose_read_and_its_90_second_bound(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _fake(monkeypatch, {45: BRIEF})
    doc = ph.build()
    [t] = doc["scheduler_timeouts"]
    assert t["read"] == "schtasks /query /fo csv /v" and t["bound_s"] == 90


def test_every_memory_figure_carries_its_host_and_total_physical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The REAL snapshot, not the fixture's: "8 GB" was once the build box read as the trading
    # box. A figure with no host and no total is ambiguous, so both are always present.
    snap = ph.memory_snapshot()
    assert snap["source"] == "psutil"
    assert isinstance(snap["host"], str) and snap["host"] and snap["host"] != "UNMEASURED"
    assert "total_phys_mb" in snap and "free_phys_mb" in snap and "commit_charge_mb" in snap
    assert snap["total_phys_mb"] is None or snap["total_phys_mb"] > 0
    import socket
    assert snap["host"] == socket.gethostname()


def test_memory_is_read_through_psutil_and_never_cim(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[Any] = []

    def spy(*a: Any, **k: Any) -> None:
        ran.append(a)

    monkeypatch.setattr(ph.subprocess, "run", spy)
    monkeypatch.setattr(ph.subprocess, "Popen", spy)
    ph.memory_snapshot()
    assert ran == [], "the memory read must not shell out (CIM / wmic / PowerShell)"
    src = (ROOT / "ops" / "process_health.py").read_text("utf-8")
    assert "Get-CimInstance" not in src.split("def memory_snapshot", 1)[1].split("\ndef ", 1)[0]


def test_an_unreadable_psutil_is_none_with_a_reason_never_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "psutil", None)   # import psutil -> ImportError
    snap = ph.memory_snapshot()
    assert snap["free_phys_mb"] is None and snap["total_phys_mb"] is None
    assert snap["commit_charge_mb"] is None and "psutil unavailable" in snap["why"]
    assert snap["host"]


def test_the_retry_runs_off_the_hot_path(monkeypatch: pytest.MonkeyPatch, box: Path) -> None:
    calls = _fake(monkeypatch, {})
    _Popen.calls = []
    monkeypatch.setattr(ph.subprocess, "Popen", _Popen)
    assert ph.main([]) == 0
    # the pass itself only ever used the hot-path bound, and did not wait on the long one
    assert calls == [("brief", 45)]
    [spawn] = _Popen.calls
    assert "--retry-scheduler" in spawn["cmd"] and "--for" in spawn["cmd"]
    assert spawn["stdin"] is subprocess.DEVNULL and spawn["stdout"] is subprocess.DEVNULL
    if sys.platform == "win32":
        assert spawn["creationflags"] & subprocess.BELOW_NORMAL_PRIORITY_CLASS
        assert spawn["creationflags"] & subprocess.DETACHED_PROCESS
    else:
        assert spawn["start_new_session"] is True
    on_disk = json.loads(ph.OUT.read_text("utf-8"))
    assert on_disk["status"] == "UNMEASURED"
    assert on_disk["scheduler_retry"]["state"] == "SPAWNED"
    assert on_disk["scheduler_retry"]["bounds_s"] == [180, 300]
    assert ph._retry_lock().exists()


def test_a_second_pass_does_not_start_a_second_retry(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _fake(monkeypatch, {})
    _Popen.calls = []
    monkeypatch.setattr(ph.subprocess, "Popen", _Popen)
    ph.main([])
    ph.main([])
    assert len(_Popen.calls) == 1
    assert json.loads(ph.OUT.read_text("utf-8"))["scheduler_retry"]["state"] == "ALREADY_RUNNING"


def test_a_pass_with_no_timeout_spawns_nothing(monkeypatch: pytest.MonkeyPatch, box: Path) -> None:
    _fake(monkeypatch, {45: BRIEF, 90: VERBOSE})
    _Popen.calls = []
    monkeypatch.setattr(ph.subprocess, "Popen", _Popen)
    ph.main([])
    assert _Popen.calls == []
    doc = json.loads(ph.OUT.read_text("utf-8"))
    assert doc["scheduler_timeouts"] == [] and doc["scheduler_retry"] == {"state": "NOT_NEEDED"}
    assert doc["status"] == "OK"


def test_a_failed_spawn_releases_the_lock_and_says_so(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _fake(monkeypatch, {})

    def boom(*a: Any, **k: Any) -> None:
        raise OSError("no")

    monkeypatch.setattr(ph.subprocess, "Popen", boom)
    ph.main([])
    assert json.loads(ph.OUT.read_text("utf-8"))["scheduler_retry"]["state"] == "SPAWN_FAILED"
    assert not ph._retry_lock().exists()


def test_the_retry_uses_the_longer_bounds_at_low_priority_and_replaces_unmeasured(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    calls = _fake(monkeypatch, {180: BRIEF, 300: VERBOSE})   # only the long bounds answer
    monkeypatch.setattr(ph.subprocess, "Popen", _Popen)
    ph.main([])
    first = json.loads(ph.OUT.read_text("utf-8"))
    assert first["status"] == "UNMEASURED"
    order: list[str] = []
    real_build = ph.build

    def lowered() -> str:
        order.append("lowered")
        return "cpu low"

    def build() -> dict[str, Any]:
        order.append("read")
        return dict(real_build())

    monkeypatch.setattr(ph, "_lower_priority", lowered)
    monkeypatch.setattr(ph, "build", build)
    out = ph.main(["--retry-scheduler", "--for", first["at"]])
    assert out == 0
    assert order == ["lowered", "read"], "priority is lowered BEFORE any scheduler read"
    assert calls[1:] == [("brief", 180), ("/v", 300)]
    doc = json.loads(ph.OUT.read_text("utf-8"))
    assert doc["status"] == "OK" and doc["run_history"] == "MEASURED"
    assert doc["scheduler_retry"]["state"] == "REPLACED"
    assert doc["scheduler_retry"]["replaced_report_at"] == first["at"]
    assert doc["scheduler_retry"]["priority"] == "cpu low"
    assert not ph._retry_lock().exists()
    # the hot-path bounds are back for the next pass
    assert ph._BOUNDS_OVERRIDE is None and ph._bound(["/query"]) == 45


def test_a_brief_only_retry_still_replaces_an_unread_inventory(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _fake(monkeypatch, {180: BRIEF})
    monkeypatch.setattr(ph.subprocess, "Popen", _Popen)
    monkeypatch.setattr(ph, "_lower_priority", lambda: "cpu low")
    ph.main([])
    ph.main(["--retry-scheduler", "--for", json.loads(ph.OUT.read_text("utf-8"))["at"]])
    doc = json.loads(ph.OUT.read_text("utf-8"))
    assert doc["scheduler_retry"]["state"] == "REPLACED"
    assert doc["scheduler_status"].startswith("OK schtasks (brief")


def test_a_retry_never_overwrites_a_newer_measured_report(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    monkeypatch.setattr(ph, "_lower_priority", lambda: "cpu low")
    _fake(monkeypatch, {45: BRIEF, 90: VERBOSE})
    ph.main([])
    newer = ph.OUT.read_text("utf-8")
    _fake(monkeypatch, {180: BRIEF, 300: VERBOSE})
    assert ph.retry_scheduler("2026-01-01T00:00:00+00:00")["state"] == "SUPERSEDED"
    assert ph.OUT.read_text("utf-8") == newer


def test_a_retry_that_reads_no_more_annotates_only_its_own_report(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    _fake(monkeypatch, {})
    monkeypatch.setattr(ph.subprocess, "Popen", _Popen)
    monkeypatch.setattr(ph, "_lower_priority", lambda: "cpu low")
    ph.main([])
    at = json.loads(ph.OUT.read_text("utf-8"))["at"]
    ph.main(["--retry-scheduler", "--for", at])
    doc = json.loads(ph.OUT.read_text("utf-8"))
    assert doc["at"] == at and doc["status"] == "UNMEASURED"
    assert doc["scheduler_retry"]["state"] == "NO_BETTER"
    [t] = doc["scheduler_retry"]["timeouts"]
    assert t["bound_s"] == 180 and t["memory"]["host"] == "TEST-BOX-1"


def test_lowering_priority_touches_only_this_process(monkeypatch: pytest.MonkeyPatch) -> None:
    psutil = pytest.importorskip("psutil")
    seen: list[int | None] = []
    real = psutil.Process

    def spy(pid: int | None = None) -> Any:
        seen.append(pid)
        return real(pid)

    monkeypatch.setattr(psutil, "Process", spy)
    # never lower the test runner itself: stub the setters on the returned handle
    monkeypatch.setattr(real, "nice", lambda self, v=None: 15 if v is None else None)
    monkeypatch.setattr(real, "ionice", lambda self, *a, **k: None)
    assert ph._lower_priority()
    assert seen == [None], "only psutil.Process() -- this process -- may be touched"
    src = (ROOT / "ops" / "process_health.py").read_text("utf-8")
    for forbidden in (".kill(", ".terminate(", "os.kill", "taskkill", ".suspend("):
        assert forbidden not in src, forbidden


def test_a_stale_lock_is_removed_as_a_file_and_a_fresh_one_is_honoured(
    monkeypatch: pytest.MonkeyPatch, box: Path
) -> None:
    import os
    lock = ph._retry_lock()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("{}", "utf-8")
    assert ph._take_retry_lock() is False
    old = lock.stat().st_mtime - ph.RETRY_LOCK_STALE_S - 5
    os.utime(lock, (old, old))
    assert ph._take_retry_lock() is True
