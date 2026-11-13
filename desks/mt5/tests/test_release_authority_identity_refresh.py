"""release_authority re-measures a stale identity AND refreshes the published mirror.

2026-11-04: the box adopted c5ddf5f11 at 18:17Z, but data/release_identity.json kept naming the
10-29 code at 147 h, because its only regular writer (the Fusion gateway pass) was paused by
the ruin rail. Adopt-And-Seal runs `release_authority --once` right after every seal, and that
pass already re-measures when the file names a different release than RELEASE.json; it now
asks release_identity's own writer to write while it does. A matching file is left alone.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from research import release_authority as ra  # noqa: E402


class _Ident:
    def __init__(self, d: dict) -> None:
        self._d = d

    def to_dict(self) -> dict:
        return dict(self._d)


def _fake_identity(monkeypatch, calls: list) -> None:
    mod = types.ModuleType("mt5desk.release_identity")

    def verdict(root, *, write=True, **_kw):
        calls.append({"root": root, "write": write})
        return _Ident({"release_id": "new", "verdict": "OK"})

    mod.verdict = verdict  # type: ignore[attr-defined]
    pkg = types.ModuleType("mt5desk")
    pkg.release_identity = mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mt5desk", pkg)
    monkeypatch.setitem(sys.modules, "mt5desk.release_identity", mod)


def test_stale_mirror_is_remeasured_and_written(monkeypatch) -> None:
    calls: list = []
    _fake_identity(monkeypatch, calls)
    out = ra._current_identity({"release_id": "old"}, {"release_id": "new"})
    assert calls == [{"root": ra.ROOT, "write": True}]
    assert out["release_id"] == "new"
    assert "old" in out["remeasured_because"]


def test_current_mirror_is_left_alone(monkeypatch) -> None:
    calls: list = []
    _fake_identity(monkeypatch, calls)
    ident = {"release_id": "same", "verdict": "OK"}
    assert ra._current_identity(ident, {"release_id": "same"}) == ident
    assert calls == []
