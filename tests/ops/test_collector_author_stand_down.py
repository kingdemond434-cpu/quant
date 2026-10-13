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
