"""The memory arm of the disk guard (gap-fixer 2026-08-26).

`/tmp` is a tmpfs on this box, so a stale scratch file holds RESIDENT MEMORY, not disk. The
guard called itself a "DISK + MEMORY GUARD" for its whole life while measuring only
`shutil.disk_usage("/")` -- so the resource that actually kills organs here (root cron
OOM-killed 08-20, the external pipeline OOM-killed 3x on 08-26, CI dead sig9 with 495MB of RAM
held under /tmp) had no instrument at all.

These tests pin the four safety properties that make deleting from /tmp legitimate. Each one
is written so that removing the corresponding guard clause makes it FAIL: a janitor whose
safety cannot be broken by a mutation is not being tested.
"""
from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts import disk_guard


def _age(path: Path, hours: float) -> None:
    old = time.time() - hours * 3600.0
    os.utime(path, (old, old))


@pytest.fixture
def tmproot(tmp_path, monkeypatch):
    monkeypatch.setattr(disk_guard, "TMP_DIR", tmp_path)
    return tmp_path


def test_stale_scratch_is_reclaimed(tmproot):
    """The thing it exists for: a week-old miner scratch file frees its RAM."""
    f = tmproot / "jodi_2002.csv"
    f.write_bytes(b"x" * 4096)
    _age(f, 148.0)
    actions: list[str] = []
    freed, n = disk_guard.reap_tmpfs(datetime.now(tz=UTC), actions)
    assert n == 1 and freed == 4096, (freed, n)
    assert not f.exists()
    assert actions and "tmpfs" in actions[0]


def test_recent_scratch_survives(tmproot):
    """A file written an hour ago may still have a writer about to reopen it."""
    f = tmproot / "in_progress.json"
    f.write_bytes(b"y" * 1024)
    _age(f, 1.0)
    freed, n = disk_guard.reap_tmpfs(datetime.now(tz=UTC), [])
    assert (freed, n) == (0, 0)
    assert f.exists()


def test_open_file_survives_however_old(tmproot):
    """SAFETY 3, and the one age alone gets wrong: a long-running seat streaming a large
    download has an ancient mtime and an open fd. Deleting it is the outage the guard is
    supposed to prevent."""
    f = tmproot / "streaming.bin"
    f.write_bytes(b"z" * 2048)
    _age(f, 500.0)
    with f.open("rb"):  # this process holds it -> it is in /proc/self/fd
        freed, n = disk_guard.reap_tmpfs(datetime.now(tz=UTC), [])
    assert (freed, n) == (0, 0), "an open file was reaped -- safety 3 is broken"
    assert f.exists()


def test_live_tool_scratch_dirs_are_never_entered(tmproot):
    """SAFETY 2: agent sessions, systemd private dirs and the pytest tmpdir tree are other
    tools' live state, not our scratch -- prefix-excluded, not age-excluded."""
    for name in ("claude-1000", "systemd-private-abc", "pytest-of-quant", "snap.foo"):
        d = tmproot / name
        d.mkdir()
        f = d / "state.json"
        f.write_bytes(b"q" * 512)
        _age(f, 900.0)
    freed, n = disk_guard.reap_tmpfs(datetime.now(tz=UTC), [])
    assert (freed, n) == (0, 0), "a live tool's scratch dir was entered"
    assert (tmproot / "claude-1000" / "state.json").exists()


def test_non_regular_files_are_never_removed(tmproot):
    """SAFETY 1: a dangling symlink is older than any cutoff and stat()s as nothing useful."""
    target = tmproot / "gone.txt"
    link = tmproot / "link.txt"
    link.symlink_to(target)
    freed, n = disk_guard.reap_tmpfs(datetime.now(tz=UTC), [])
    assert (freed, n) == (0, 0)
    assert link.is_symlink()


def test_nested_stale_scratch_is_reached(tmproot):
    """Seats write into their own subdirectories (/tmp/okxc/*.zip was 4MB of dead RAM)."""
    d = tmproot / "okxc"
    d.mkdir()
    f = d / "2022-01-01.zip"
    f.write_bytes(b"w" * 8192)
    _age(f, 166.0)
    freed, n = disk_guard.reap_tmpfs(datetime.now(tz=UTC), [])
    assert (freed, n) == (8192, 1)


def test_mem_available_is_read_and_positive():
    """The arm's instrument. 0.0 means blind, which the report escalates rather than passes."""
    assert disk_guard.mem_available_mb() > 0.0


def test_unreadable_meminfo_is_a_defect_not_a_pass(tmp_path, monkeypatch):
    """UNMEASURED is a real answer (L1.28a): a blind memory arm must not read as healthy.

    Every production path is redirected first. A test that rolls up the desk's real discovery
    corpus to assert something about a report is the suite-reverts-writes class, and this file
    would be the third instance."""
    monkeypatch.setattr(disk_guard, "mem_available_mb", lambda: 0.0)
    monkeypatch.setattr(disk_guard, "TMP_DIR", tmp_path / "absent")
    monkeypatch.setattr(disk_guard, "INTEL_DIRS", [tmp_path / "intel-absent"])
    monkeypatch.setattr(disk_guard, "LOG", tmp_path / "disk_guard.json")
    rc = disk_guard.main()
    report = disk_guard.json.loads(disk_guard.LOG.read_text("utf-8"))
    assert "MEM_ALERT" in report and "UNREADABLE" in report["MEM_ALERT"]
    assert rc == 1, "a blind guard returned success"
