"""Kernel-log readability fence (R0350) -- UNMEASURED must never read as OK.

The fence's whole value is the direction of its failure: a box where no kernel-log channel is
readable must page (exit 2), never pass, because every "no OOM" conclusion drawn there is void.
These tests mock subprocess at the module boundary and pin (a) readable dmesg -> exit 0 READABLE,
(b) all channels denied -> exit 2 UNREADABLE, and (c) a stable artifact schema, including the
L1.40 heart: a probe that exits 0 with zero kernel lines is NOT a readable channel.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SRC = Path(__file__).resolve().parents[2] / "scripts/check_kernel_log.py"

_DENIED = "dmesg: read kernel buffer failed: Operation not permitted"
_NO_JOURNAL = "No journal files were found."
_RING = "[Tue Aug  4 19:57:01 2026] Linux version 6.18.5\n[Tue Aug  4 19:57:02 2026] OOM? no.\n"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_kernel_log_probe", _SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_run(replies: dict[str, tuple[int, str, str]]) -> Callable[..., Any]:
    """A subprocess.run stand-in keyed on the probed binary name."""

    def run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        rc, out, err = replies[cmd[0]]
        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr=err)

    return run


@pytest.fixture
def mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    m = _load()
    monkeypatch.setattr(m, "_OUT", tmp_path / "data/kernel_log_status.json")
    monkeypatch.setattr("sys.argv", ["check_kernel_log.py"])
    return m


def test_dmesg_readable_exits_0_verdict_readable(mod: ModuleType, tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    # The 2026-08-04 box: dmesg ring readable, journald absent. One channel is enough.
    monkeypatch.setattr(mod.subprocess, "run", _fake_run({
        "dmesg": (0, _RING, ""),
        "journalctl": (0, "", _NO_JOURNAL),
    }))
    assert mod.main() == 0
    rep = json.loads((tmp_path / "data/kernel_log_status.json").read_text("utf-8"))
    assert rep["verdict"] == "READABLE"
    assert rep["readable_channels"] == ["dmesg"]
    dmesg = next(c for c in rep["channels"] if c["channel"] == "dmesg")
    assert dmesg["readable"] is True and dmesg["lines_seen"] == 2


def test_all_channels_denied_exits_2_verdict_unreadable(
        mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # The 2026-08-01 box: dmesg denied outright, journal empty. The fence FIRES -- exit 2 is the
    # instrument reporting its own absence, and it must page rather than pass.
    monkeypatch.setattr(mod.subprocess, "run", _fake_run({
        "dmesg": (1, "", _DENIED),
        "journalctl": (0, "-- No entries --\n", ""),
    }))
    assert mod.main() == 2
    rep = json.loads((tmp_path / "data/kernel_log_status.json").read_text("utf-8"))
    assert rep["verdict"] == "UNREADABLE"
    assert rep["readable_channels"] == []
    assert all(c["readable"] is False for c in rep["channels"])
    assert "PAGE" in capsys.readouterr().out


def test_exit_0_with_zero_lines_is_not_readable(mod: ModuleType,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    # The L1.40 heart: a probe that SUCCEEDS but shows nothing proves nothing. rc 0 + empty
    # ring must not be counted as a readable channel, or an empty read becomes a green light.
    monkeypatch.setattr(mod.subprocess, "run", _fake_run({
        "dmesg": (0, "", ""),
        "journalctl": (0, "", _NO_JOURNAL),
    }))
    rep = mod.build_report()
    assert rep["verdict"] == "UNREADABLE"
    dmesg = next(c for c in rep["channels"] if c["channel"] == "dmesg")
    assert dmesg["readable"] is False and dmesg["returncode"] == 0
    assert "empty read" in dmesg["note"] or "zero kernel lines" in dmesg["note"]


def test_probe_exceptions_become_data_not_crashes(mod: ModuleType,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    # A missing binary or an exec-time PermissionError is a finding, never a traceback.
    def raise_run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] == "dmesg":
            raise PermissionError("EACCES")
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(mod.subprocess, "run", raise_run)
    rep = mod.build_report()
    assert rep["verdict"] == "UNREADABLE"
    for ch in rep["channels"]:
        assert ch["readable"] is False and ch["returncode"] is None
        assert ch["note"] != ""


def test_artifact_schema_is_stable(mod: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Downstream kill-diagnosis organs read this artifact; its shape is a contract.
    monkeypatch.setattr(mod.subprocess, "run", _fake_run({
        "dmesg": (0, _RING, ""),
        "journalctl": (0, _RING, ""),
    }))
    rep = mod.build_report()
    assert set(rep) == {"generated", "law", "verdict", "detail", "readable_channels",
                        "channels", "next_action"}
    assert rep["verdict"] in {"READABLE", "UNREADABLE"}
    stamp = datetime.fromisoformat(rep["generated"])
    assert stamp.tzinfo is not None                      # timezone-aware, always
    assert [c["channel"] for c in rep["channels"]] == ["dmesg", "journalctl-k"]
    for ch in rep["channels"]:
        assert set(ch) == {"channel", "command", "probed_at", "returncode",
                           "lines_seen", "readable", "note"}
        probed = datetime.fromisoformat(ch["probed_at"])
        assert probed.tzinfo is not None


def test_report_only_never_fails_the_cron(mod: ModuleType,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.subprocess, "run", _fake_run({
        "dmesg": (1, "", _DENIED),
        "journalctl": (1, "", _DENIED),
    }))
    monkeypatch.setattr("sys.argv", ["check_kernel_log.py", "--report-only"])
    assert mod.main() == 0                               # recorded, not paged, by request
