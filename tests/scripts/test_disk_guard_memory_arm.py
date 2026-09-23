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


# ---------------------------------------------------------------------------------------------
# PRESSURE-ADAPTIVE RETENTION (gap-fixer 2026-08-29). The arm above was correct and the box died
# anyway. MEASURED: /tmp held 941MB with MemAvailable at 261MB and this reaper freed ZERO -- every
# large holder was 8-14h old against the 24h window and the 297MB orphaned law-gate checkout was
# 20 MINUTES old against the 12h one. Working exactly as designed, every sweep, while 141 oom-kills
# landed in 7 days (74 on desk organs). These tests pin the ages that actually occurred.
# ---------------------------------------------------------------------------------------------


def _redirect(monkeypatch, tmp_path, tmproot):
    """Every production path off the live box first (the suite-reverts-writes class)."""
    monkeypatch.setattr(disk_guard, "TMP_DIR", tmproot)
    monkeypatch.setattr(disk_guard, "INTEL_DIRS", [tmp_path / "intel-absent"])
    monkeypatch.setattr(disk_guard, "LOG", tmp_path / "disk_guard.json")
    monkeypatch.setattr(disk_guard, "REPO", tmp_path / "repo-absent")
    monkeypatch.setattr(disk_guard, "tmpfs_used_mb", lambda: 0.0)


def _mem_sequence(monkeypatch, values):
    """MemAvailable readings in call order; the last one repeats forever."""
    seen = list(values)
    monkeypatch.setattr(disk_guard, "mem_available_mb",
                        lambda: seen.pop(0) if len(seen) > 1 else seen[0])


def test_young_scratch_is_reclaimed_when_the_box_is_under_its_floor(tmproot, tmp_path,
                                                                    monkeypatch):
    """THE DEFECT ITSELF. A 9h-old download is exactly what sat on the live box unreclaimed."""
    f = tmproot / "speeches.zip"
    f.write_bytes(b"x" * 8192)
    _age(f, 9.0)
    # Standing policy declines it, and that is CORRECT on a box with headroom.
    assert disk_guard.reap_tmpfs(datetime.now(tz=UTC), [])[1] == 0
    assert f.exists(), "the 24h window is the standing policy and must not change"
    # Under the floor, the ladder reaches it.
    _redirect(monkeypatch, tmp_path, tmproot)
    _mem_sequence(monkeypatch, [261.0])
    disk_guard.main()
    assert not f.exists(), "9h-old scratch survived a box under its own MemAvailable floor"


def test_healthy_box_never_escalates(tmproot, tmp_path, monkeypatch):
    """The other half, and the one that keeps this from being a licence: with headroom the
    ladder is never entered and the 24h window is the whole policy."""
    f = tmproot / "in_progress.json"
    f.write_bytes(b"y" * 4096)
    _age(f, 9.0)
    _redirect(monkeypatch, tmp_path, tmproot)
    _mem_sequence(monkeypatch, [1500.0])
    disk_guard.main()
    assert f.exists(), "a box with headroom reaped below its standing retention window"
    report = disk_guard.json.loads(disk_guard.LOG.read_text("utf-8"))
    assert report["retention_escalations"] == []


def test_ladder_stops_the_moment_the_floor_clears(tmproot, tmp_path, monkeypatch):
    """Escalation is bounded by need, not run to the bottom rung on principle."""
    old, young = tmproot / "ff.csv", tmproot / "fresh.json"
    old.write_bytes(b"a" * 2048)
    young.write_bytes(b"b" * 2048)
    _age(old, 13.0)     # inside rung 1 (12h)
    _age(young, 5.0)    # only rung 2 (6h) or lower would take it
    _redirect(monkeypatch, tmp_path, tmproot)
    _mem_sequence(monkeypatch, [261.0, 261.0, 900.0])
    disk_guard.main()
    assert not old.exists(), "rung 1 (12h) did not run while the box was under its floor"
    assert young.exists(), "the ladder kept descending after the floor had cleared"
    report = disk_guard.json.loads(disk_guard.LOG.read_text("utf-8"))
    assert len(report["retention_escalations"]) == 1, report["retention_escalations"]


def test_open_file_survives_the_bottom_rung(tmproot, tmp_path, monkeypatch):
    """SAFETY IS NOT WHAT YIELDS. Escalation moves the AGE heuristic only; a file a live process
    holds open is untouchable at every rung, which is the clause age alone gets wrong."""
    f = tmproot / "streaming_download.bin"
    f.write_bytes(b"z" * 4096)
    _age(f, 200.0)
    _redirect(monkeypatch, tmp_path, tmproot)
    _mem_sequence(monkeypatch, [100.0])
    with f.open("rb"):
        disk_guard.main()
        assert f.exists(), "the bottom rung deleted a file a live process held open"


def test_alert_splits_producer_pressure_from_resident_pressure(tmproot, tmp_path, monkeypatch):
    """THE INFERENCE THAT HID THIS FOR 16 DAYS. 'The reap freed little' does NOT imply the
    pressure is resident -- while /tmp is still large it means the scratch is YOUNG. The old
    text rendered both states identically and routed a fixable, in-scope defect to a root
    swapfile at the principal's console."""
    _redirect(monkeypatch, tmp_path, tmproot)
    _mem_sequence(monkeypatch, [100.0])

    monkeypatch.setattr(disk_guard, "tmpfs_used_mb", lambda: 900.0)
    disk_guard.main()
    producer = disk_guard.json.loads(disk_guard.LOG.read_text("utf-8"))["MEM_ALERT"]
    assert "PRODUCER problem" in producer and "swapfile" not in producer

    monkeypatch.setattr(disk_guard, "tmpfs_used_mb", lambda: 12.0)
    disk_guard.main()
    resident = disk_guard.json.loads(disk_guard.LOG.read_text("utf-8"))["MEM_ALERT"]
    assert "swapfile" in resident and "PRODUCER problem" not in resident


def test_tmpfs_used_mb_distinguishes_not_a_tmpfs_from_empty(monkeypatch):
    """None (not a tmpfs -- no hidden RAM here) must never render as 0.0 (a tmpfs that is
    empty). Folding them would make the alert claim resident pressure on any normal host."""
    assert disk_guard.tmpfs_used_mb() is not None, "/tmp is a tmpfs on this box"
    monkeypatch.setattr(disk_guard.Path, "read_text", lambda *a, **k: "/dev/sda1 /tmp ext4 rw 0 0")
    assert disk_guard.tmpfs_used_mb() is None
