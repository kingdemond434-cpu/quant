"""collector_author STANDS DOWN (2026-10-13): no model-written code runs from it.

A canary beat its regex deny-list and its runner inherited every key. Until it is ported into the
LLM lab's isolated code path, `main()` must record a STAND_DOWN without calling a model and
`run_isolated()` must refuse without starting a process.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import collector_author as ca

CANARY = 'def fetch():\n    __builtins__["__imp"+"ort__"]("o"+"s").popen("id")\n    return {}\n'


def _boom(*a: Any, **k: Any) -> Any:
    raise AssertionError("collector_author executed or asked a model while stood down")


def test_runner_refuses_the_canary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _boom)
    series, msg = ca.run_isolated(CANARY)
    assert series is None and msg.startswith("STAND_DOWN")


def test_main_records_the_stand_down_and_calls_nothing(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ca, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(ca.seats, "resolve", _boom)
    monkeypatch.setattr(ca.urllib.request, "urlopen", _boom)
    ca.main()
    assert json.loads((tmp_path / "status.json").read_text())["status"] == "STAND_DOWN"


def test_the_stood_down_bodies_have_no_caller() -> None:
    """Audit should-fix on #362: a later edit must not quietly re-wire the unsafe bodies."""
    import re
    root = Path(__file__).resolve().parents[2]
    names = ("_run_isolated_unsafe_stood_down", "_main_unsafe_stood_down")
    for path in [*root.glob("scripts/**/*.py"), *root.glob("libs/**/*.py"),
                 *root.glob("desks/**/*.py")]:
        text = path.read_text("utf-8", errors="ignore")
        for n in names:
            calls = [m for m in re.finditer(rf"\b{n}\s*\(", text)
                     if not text[max(0, m.start() - 4):m.start()].endswith("def ")]
            assert not calls, f"{path}: calls {n}"
