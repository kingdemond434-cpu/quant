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


def test_a_held_target_is_never_written_in_place(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """Audit must-fix on 37bb136b4: after the retries the writer RAISES and keeps the temp
    file; the old target is untouched, never torn by an in-place write."""
    path = tmp_path / "state.json"
    path.write_text('{"old": 1}\n', encoding="utf-8")

    def refuse(src: object, dst: object) -> None:
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(aj.os, "replace", refuse)
    monkeypatch.setattr(aj.time, "sleep", lambda s: None)
    with pytest.raises(aj.ReplaceFailed) as err:
        aj.write_json(path, {"a": 1})
    assert json.loads(path.read_text("utf-8")) == {"old": 1}
    kept = list(tmp_path.glob("*.tmp"))
    assert kept == [err.value.tmp] and json.loads(kept[0].read_text("utf-8")) == {"a": 1}
    assert str(err.value.tmp) in str(err.value)


def test_the_lock_serialises_and_a_dead_holder_never_blocks(tmp_path: Path) -> None:
    """Audit should-fix 1 on 4e4cdc972: the OS holds the lock, so a holder that died leaves
    nothing to break, and a live holder in another process blocks until it releases."""
    import subprocess
    import sys
    path = tmp_path / "evidence_start.json"
    with aj.locked(path), pytest.raises(TimeoutError), aj.locked(path, timeout_s=0.1):
        pass
    lock = path.with_name(path.name + ".lock")
    assert lock.exists(), "the lock file stays; only the OS lock is released"
    with aj.locked(path, timeout_s=1.0):
        pass                                   # a leftover file is not a held lock
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time; sys.path.insert(0, sys.argv[2]); from libs.ops import atomic_json "
         "as aj; from pathlib import Path\n"
         "with aj.locked(Path(sys.argv[1])):\n    print('held', flush=True); time.sleep(30)",
         str(path), str(Path(aj.__file__).resolve().parents[2])],
        stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "held"
        with pytest.raises(TimeoutError), aj.locked(path, timeout_s=0.2):
            pass
        holder.kill()
        holder.wait(timeout=10)
        with aj.locked(path, timeout_s=2.0):
            pass                               # the holder died; the OS released its lock
    finally:
        holder.kill()


def test_a_kept_temp_is_swept_after_a_day(tmp_path: Path) -> None:
    """Audit should-fix 2 on 4e4cdc972."""
    path = tmp_path / "state.json"
    old = tmp_path / "state.json.1.2.deadbeef.tmp"
    new = tmp_path / "state.json.1.2.cafebabe.tmp"
    other = tmp_path / "other.json.1.2.deadbeef.tmp"
    for f in (old, new, other):
        f.write_text("{}")
    stale = old.stat().st_mtime - aj.TMP_SWEEP_S - 5
    os.utime(old, (stale, stale))
    os.utime(other, (stale, stale))
    aj.write_json(path, {"a": 1})
    assert not old.exists() and new.exists() and other.exists()
