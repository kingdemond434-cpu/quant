"""MONEY RUNS ABOVE RESEARCH (libs/ops/money_priority.py): every money and prop runner enters the
ABOVE_NORMAL job, the job limit is the priority class and nothing else, and it never breaks a
runner."""

from __future__ import annotations

import ctypes
import re
import sys
from pathlib import Path

import pytest

from libs.ops import money_priority as mp

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "desks/mt5/ops/box_tasks.manifest"
_ROW = re.compile(r'^TASK name="([^"]+)".*?runs="([^"]+)".*?lane="(money|prop)"', re.M)


def _money_runners() -> list[tuple[str, str]]:
    out = []
    for name, runs, _lane in _ROW.findall(MANIFEST.read_text(encoding="utf-8")):
        script = runs.split()[0]
        if script.endswith(".py"):
            out.append((name, script))
    return out


def test_the_manifest_has_money_runners() -> None:
    names = {n for n, _ in _money_runners()}
    assert {"E8-Gold", "E8-Executor", "MT5-FTMO-Executor", "MT5-FTMO-Follower"} <= names


@pytest.mark.parametrize("name,script", _money_runners())
def test_every_money_runner_enters_the_money_job(name: str, script: str) -> None:
    if script in mp.CANON_EXEMPT:
        pytest.skip("canon copy of a box original: wrapped by the CLI instead")
    src = (ROOT / script).read_text(encoding="utf-8")
    assert "from libs.ops.money_priority import enter" in src, f"{name} ({script})"
    assert "_money_priority()" in src, f"{name} ({script})"


def test_the_canon_exemptions_are_real_canon_copies() -> None:
    for script in mp.CANON_EXEMPT:
        head = (ROOT / script).read_text(encoding="utf-8").splitlines()[0]
        assert head.startswith("# CANON COPY"), script


def test_the_job_limit_is_the_priority_class_and_nothing_else() -> None:
    info = mp.limits()
    basic = info.BasicLimitInformation
    assert basic.LimitFlags == mp.JOB_OBJECT_LIMIT_PRIORITY_CLASS == 0x20
    assert basic.PriorityClass == mp.ABOVE_NORMAL_PRIORITY_CLASS == 0x8000
    assert basic.ActiveProcessLimit == 0 and basic.Affinity == 0  # no cap, no core pinning
    assert info.ProcessMemoryLimit == 0 and info.JobMemoryLimit == 0
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        assert ctypes.sizeof(info) == 144  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION on x64


def test_enter_is_safe_and_idempotent_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mp, "_STATE", {})
    if sys.platform != "win32":
        assert mp.enter() == "not Windows: nothing changed"
    first = mp.enter()
    assert mp.enter() == first


def test_a_failure_never_breaks_the_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform == "win32":
        pytest.skip("exercises the failure path off Windows")
    monkeypatch.setattr(mp, "_STATE", {})
    monkeypatch.setattr(mp, "_windows", lambda: True)  # no kernel32 here: every call fails
    got = mp.enter()
    assert got.startswith("unchanged (")


def test_the_cli_runs_the_command_and_returns_its_code() -> None:
    assert mp.main(["--", sys.executable, "-c", "raise SystemExit(3)"]) == 3
    assert mp.main([]) == 2
