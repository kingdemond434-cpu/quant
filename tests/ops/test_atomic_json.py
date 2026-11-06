"""Atomic JSON writes: no shared temp name, a WinError-5 fallback, and a read-modify-write lock
(audit of 538cb964, SF11)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from libs.ops import atomic_json as aj


def test_concurrent_writers_never_leave_a_torn_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    errors: list[BaseException] = []

    def write(i: int) -> None:
        try:
            for k in range(30):
                aj.write_json(path, {"writer": i, "k": k, "pad": "x" * 2000})
        except BaseException as exc:            # pragma: no cover - the assertion reports it
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert json.loads(path.read_text("utf-8"))["pad"] == "x" * 2000
    assert list(tmp_path.glob("*.tmp")) == []


def test_a_held_target_falls_back_to_an_in_place_write(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "state.json"

    def refuse(src: object, dst: object) -> None:
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(aj.os, "replace", refuse)
    monkeypatch.setattr(aj.time, "sleep", lambda s: None)
    aj.write_json(path, {"a": 1})
    assert json.loads(path.read_text("utf-8")) == {"a": 1}
    assert list(tmp_path.glob("*.tmp")) == []


def test_the_lock_serialises_and_breaks_a_stale_holder(tmp_path: Path) -> None:
    path = tmp_path / "evidence_start.json"
    with aj.locked(path), pytest.raises(TimeoutError), aj.locked(path, timeout_s=0.1):
        pass
    lock = path.with_name(path.name + ".lock")
    lock.write_text("")
    old = lock.stat().st_mtime - aj.STALE_LOCK_S - 5
    os.utime(lock, (old, old))
    with aj.locked(path, timeout_s=1.0):
        assert lock.exists()
    assert not lock.exists()
