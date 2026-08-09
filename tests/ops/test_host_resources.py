"""TMPFS IS RAM THAT BELONGS TO NO PROCESS, AND THE READER MUST NEVER FABRICATE A ZERO.

The failure this guards is not "the number is slightly wrong". It is that an UNMEASURABLE box
renders identically to a HEALTHY one -- `None` quietly becoming `0MB` turns "we could not read
/proc" into "there was no memory pressure", which is the exact inversion that let 1021MB of
orphaned pytest scratch sit unnoticed on a 3.8GB swapless box while every memory check on the desk
reported fine. Every test here pins a DISTINCTION, not a value.
"""

from __future__ import annotations

import os
from pathlib import Path

from libs.ops import host_resources as hr


class TestUnmeasurableNeverRendersAsZero:
    def test_unreadable_meminfo_is_none_not_zero(self, monkeypatch):
        """`None` and `0` are different answers about the box and must stay different."""
        monkeypatch.setattr(Path, "read_text",
                            lambda self, *a, **k: (_ for _ in ()).throw(OSError("no /proc")))
        assert hr.mem_available_mb() is None

    def test_garbled_meminfo_is_none_not_zero(self, monkeypatch):
        """A malformed field must not parse to 0 -- that reads as 'no memory left' and pages."""
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "MemAvailable:  notanumber\n")
        assert hr.mem_available_mb() is None

    def test_reads_the_real_value_where_proc_exists(self):
        got = hr.mem_available_mb()
        if Path("/proc/meminfo").exists():
            assert isinstance(got, int) and got >= 0

    def test_non_tmpfs_path_is_none_not_zero(self, tmp_path, monkeypatch):
        """'This measurement does not apply' must not render as '0MB of tmpfs pressure'."""
        monkeypatch.setattr(hr, "_fstype", lambda _p: "ext4")
        assert hr.tmpfs_used_mb(str(tmp_path)) is None

    def test_unreadable_mounts_is_none(self, monkeypatch):
        monkeypatch.setattr(Path, "read_text",
                            lambda self, *a, **k: (_ for _ in ()).throw(OSError("no /proc")))
        assert hr.tmpfs_used_mb("/tmp") is None


class TestMountResolution:
    def test_longest_prefix_wins(self, monkeypatch):
        """`/` and `/tmp` are both prefixes of `/tmp/x`; only the longer one carries the file.

        Getting this backwards reports the ROOT filesystem's type for a tmpfs path, which is how a
        tmpfs stops being measured at all.
        """
        monkeypatch.setattr(hr, "_MOUNTS", Path("/dev/null"))
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (
            "/dev/sda1 / ext4 rw 0 0\n"
            "tmpfs /tmp tmpfs rw 0 0\n"))
        assert hr._fstype("/tmp/pytest-of-quant") == "tmpfs"
        assert hr._fstype("/home/quant") == "ext4"

    def test_prefix_is_not_a_substring_match(self, monkeypatch):
        """`/tmpfoo` is NOT under `/tmp`, and a naive startswith says it is."""
        monkeypatch.setattr(hr, "_MOUNTS", Path("/dev/null"))
        monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (
            "/dev/sda1 / ext4 rw 0 0\n"
            "tmpfs /tmp tmpfs rw 0 0\n"))
        assert hr._fstype("/tmpfoo/bar") == "ext4"

    def test_real_tmp_is_measured_when_it_is_a_tmpfs(self):
        """On this box /tmp IS a tmpfs; if that ever stops being true the reader must say so."""
        if hr._fstype("/tmp") == "tmpfs":
            used = hr.tmpfs_used_mb("/tmp")
            assert isinstance(used, int) and used >= 0


class TestPressureNoteIsSafeOnTheFailurePath:
    def test_never_raises_when_nothing_is_readable(self, monkeypatch):
        """It is called while reporting a kill; an instrument that throws there loses the cause."""
        monkeypatch.setattr(Path, "read_text",
                            lambda self, *a, **k: (_ for _ in ()).throw(OSError("no /proc")))
        monkeypatch.setattr(os, "statvfs",
                            lambda _p: (_ for _ in ()).throw(OSError("gone")))
        note = hr.pressure_note()
        assert note and "unknown" in note

    def test_names_the_tmpfs_ram_when_present(self, monkeypatch):
        monkeypatch.setattr(hr, "mem_available_mb", lambda: 189)
        monkeypatch.setattr(hr, "tmpfs_used_mb", lambda _p="/tmp": 1021)
        note = hr.pressure_note()
        assert "189MB" in note and "1021MB" in note and "tmpfs" in note

    def test_distinguishes_not_a_tmpfs_from_empty_tmpfs(self, monkeypatch):
        monkeypatch.setattr(hr, "mem_available_mb", lambda: 500)
        monkeypatch.setattr(hr, "tmpfs_used_mb", lambda _p="/tmp": None)
        assert "not a tmpfs" in hr.pressure_note()
        monkeypatch.setattr(hr, "tmpfs_used_mb", lambda _p="/tmp": 0)
        assert "0MB of RAM held" in hr.pressure_note()
