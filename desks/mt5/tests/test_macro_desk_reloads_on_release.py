"""A perpetual macro_desk must not outlive the code it was started on.

research_supervisor launches `macro_desk.main` once and it loops forever, so it executes whatever
was on disk at START. MT5-AdoptRelease restarts only the gateway, which is how the per-cell anchor
merge (97e21ce8f) reached the box's disk and never the running process: the branch's
`cross_asset_anchors.pkl` stayed with T10YIE all NaN. The loop now ends when its code changes, and
the supervisor respawns it on the adopted release.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import macro_desk  # noqa: E402


def test_the_loop_exits_when_its_code_changes(monkeypatch) -> None:
    prints = iter([("a",), ("b",)])
    monkeypatch.setattr(macro_desk, "_code_fingerprint", lambda: next(prints))
    ran: list[str] = []
    monkeypatch.setattr(macro_desk, "anchors", lambda: ran.append("anchors"))
    monkeypatch.setattr(macro_desk, "log", lambda msg: None)
    macro_desk.main()
    assert ran == [], "a stale copy ran a cycle after its code was replaced on disk"


def test_unchanged_code_keeps_cycling(monkeypatch) -> None:
    monkeypatch.setattr(macro_desk, "_code_fingerprint", lambda: ("same",))
    ran: list[str] = []

    class _Stop(BaseException):
        pass

    def _anchors() -> None:
        ran.append("anchors")

    def _sleep(_s: float) -> None:
        raise _Stop

    monkeypatch.setattr(macro_desk, "anchors", _anchors)
    monkeypatch.setattr(macro_desk, "build_state", lambda: None)
    monkeypatch.setattr(macro_desk, "pit_backfill", lambda: None)
    monkeypatch.setattr(macro_desk, "log", lambda msg: None)
    monkeypatch.setattr(macro_desk.time, "sleep", _sleep)
    with pytest.raises(_Stop):
        macro_desk.main()
    assert ran == ["anchors"], "the fingerprint check stopped a desk whose code had not changed"


def test_the_fingerprint_reads_this_module() -> None:
    names = [p for p, _ in macro_desk._code_fingerprint()]
    assert any(p.endswith("macro_desk.py") for p in names)
