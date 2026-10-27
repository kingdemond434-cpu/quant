"""THE CLEAR-RECORD FENCE FIRES ON A BAD RECORD AND STAYS QUIET ON A SHALLOW CLONE."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_seal_clears", ROOT / "scripts" / "check_seal_clears.py"
)
assert SPEC and SPEC.loader
fence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fence)


def _raise(exc: Exception) -> Callable[..., str]:
    def f(*_: object) -> str:
        raise exc

    return f


def test_shallow_clone_is_unmeasured_not_a_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence.sign_train, "_git", lambda *a: "0" * 40)
    monkeypatch.setattr(
        fence.sign_train, "_committed_clears", _raise(ValueError("shallow clone: cannot prove"))
    )
    assert fence.judge()["verdict"] == "UNMEASURED"
    assert fence.main([]) == 0


def test_a_rewritten_record_is_a_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence.sign_train, "_git", lambda *a: "0" * 40)
    monkeypatch.setattr(
        fence.sign_train,
        "_committed_clears",
        _raise(ValueError("an earlier committed record is not kept")),
    )
    assert fence.judge()["verdict"] == "BREACH"
    assert fence.main([]) == 1


def test_a_garbled_row_is_a_breach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence.sign_train, "_git", lambda *a: "0" * 40)
    monkeypatch.setattr(fence.sign_train, "_committed_clears", lambda head: "not json\n")
    assert fence.judge()["verdict"] == "BREACH"


def test_an_empty_record_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fence.sign_train, "_git", lambda *a: "0" * 40)
    monkeypatch.setattr(fence.sign_train, "_committed_clears", lambda head: "")
    assert fence.judge()["verdict"] == "PASS"
