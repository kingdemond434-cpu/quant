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


class TestHolderVerdictNeverCertifiesWhatItCannotSee:
    """The one test that matters: a PARTIAL fd scan must never say "held by nothing".

    Measured on this box, 42 of 175 pids are fd-readable. A two-valued flag would certify the
    scratch of the other 133 as unheld and the reader would delete a live session's working
    state -- under memory pressure, which is exactly when the mistake is likeliest.
    """

    def _tmpfs(self, monkeypatch, tmp_path):
        monkeypatch.setattr(hr, "_fstype", lambda _p: "tmpfs")
        big = tmp_path / "scratch.bin"
        big.write_bytes(b"x" * (12 * 1024 * 1024))
        return big

    def test_partial_coverage_reports_unknown_not_false(self, tmp_path, monkeypatch):
        self._tmpfs(monkeypatch, tmp_path)
        monkeypatch.setattr(hr, "fd_scan_coverage", lambda: (42, 175))
        monkeypatch.setattr(hr, "_held_paths", lambda _m: set())
        [row] = hr.tmpfs_top_holders(str(tmp_path))
        assert row.held is None, "a partial scan must not certify an entry as unheld"

    def test_full_coverage_may_assert_unheld(self, tmp_path, monkeypatch):
        self._tmpfs(monkeypatch, tmp_path)
        monkeypatch.setattr(hr, "fd_scan_coverage", lambda: (175, 175))
        monkeypatch.setattr(hr, "_held_paths", lambda _m: set())
        [row] = hr.tmpfs_top_holders(str(tmp_path))
        assert row.held is False

    def test_zero_pids_is_not_full_coverage(self, tmp_path, monkeypatch):
        """An unreadable /proc yields (0, 0); `readable == total` is True and must NOT mean seen."""
        self._tmpfs(monkeypatch, tmp_path)
        monkeypatch.setattr(hr, "fd_scan_coverage", lambda: (0, 0))
        monkeypatch.setattr(hr, "_held_paths", lambda _m: set())
        [row] = hr.tmpfs_top_holders(str(tmp_path))
        assert row.held is None

    def test_a_live_holder_is_a_fact_at_any_coverage(self, tmp_path, monkeypatch):
        big = self._tmpfs(monkeypatch, tmp_path)
        monkeypatch.setattr(hr, "fd_scan_coverage", lambda: (1, 175))
        monkeypatch.setattr(hr, "_held_paths", lambda _m: {str(big)})
        [row] = hr.tmpfs_top_holders(str(tmp_path))
        assert row.held is True

    def test_a_holder_inside_a_directory_holds_the_directory(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "_fstype", lambda _p: "tmpfs")
        d = tmp_path / "session"
        d.mkdir()
        (d / "task.output").write_bytes(b"y" * (11 * 1024 * 1024))
        monkeypatch.setattr(hr, "fd_scan_coverage", lambda: (175, 175))
        monkeypatch.setattr(hr, "_held_paths", lambda _m: {str(d / "task.output")})
        [row] = hr.tmpfs_top_holders(str(tmp_path))
        assert row.path == str(d) and row.held is True, "an open fd inside pins the whole dir"

    def test_non_tmpfs_yields_no_rows_to_act_on(self, tmp_path, monkeypatch):
        self._tmpfs(monkeypatch, tmp_path)
        monkeypatch.setattr(hr, "_fstype", lambda _p: "ext4")
        assert hr.tmpfs_top_holders(str(tmp_path)) == []

    def test_small_entries_are_not_reported(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "_fstype", lambda _p: "tmpfs")
        (tmp_path / "tiny").write_bytes(b"z" * 1024)
        assert hr.tmpfs_top_holders(str(tmp_path)) == []

    def test_coverage_is_readable_over_total_on_the_real_box(self):
        readable, total = hr.fd_scan_coverage()
        assert 0 <= readable <= total


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
