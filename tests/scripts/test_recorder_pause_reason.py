"""The recorder fences must READ why writing stopped, not assert it.

Three causes rendered as one message before 2026-08-20: a genuine stall, a deliberate disk pause,
and the desk's own kill switch. Only the first is this defect, and the third had welded the
principal's ACCEPT path shut -- data/RECORDERS_OFF is the file data/PRINCIPAL_ACTION.md tells them
to touch to accept the crypto-tape retirement, and max_audit had never heard of it.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

max_audit = importlib.import_module("scripts.max_audit")


@pytest.fixture
def fake_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(max_audit, "ROOT", tmp_path)
    return tmp_path


class TestRecorderPauseReason:
    def test_writing_normally_reports_no_reason(self, fake_root: Path) -> None:
        (fake_root / "data/recorder_heartbeat").write_text("2026-08-20T08:00:41+00:00")
        assert max_audit._recorder_pause_reason() == ""

    def test_no_heartbeat_at_all_is_not_evidence_of_a_pause(self, fake_root: Path) -> None:
        """A genuine stall must keep firing the original defect -- this loosens nothing."""
        assert max_audit._recorder_pause_reason() == ""

    def test_disk_paused_marker_is_read(self, fake_root: Path) -> None:
        """Measured live 2026-08-20: '<iso> DISK-PAUSED', republished every 30s."""
        (fake_root / "data/recorder_heartbeat").write_text(
            "2026-08-20T08:00:41.173789+00:00 DISK-PAUSED")
        assert max_audit._recorder_pause_reason() == "DISK-PAUSED"

    def test_any_of_the_three_recorders_pausing_is_seen(self, fake_root: Path) -> None:
        """bybit stamps an epoch float, not an ISO string -- the marker is what matters."""
        (fake_root / "data/recorder_bybit_heartbeat").write_text("1787212859.32 DISK-PAUSED")
        assert max_audit._recorder_pause_reason() == "DISK-PAUSED"

    def test_kill_switch_outranks_a_disk_pause(self, fake_root: Path) -> None:
        (fake_root / "data/RECORDERS_OFF").write_text("")
        (fake_root / "data/recorder_heartbeat").write_text("2026-08-20T08:00:41+00:00 DISK-PAUSED")
        assert max_audit._recorder_pause_reason() == "SWITCHED-OFF"

    def test_unreadable_heartbeat_is_not_a_pause(self, fake_root: Path) -> None:
        """An unreadable marker is UNMEASURED; it must not manufacture a clean excuse (L1.28a)."""
        (fake_root / "data/recorder_heartbeat").mkdir()      # a directory: read_text raises OSError
        assert max_audit._recorder_pause_reason() == ""


class TestScopeCheckNamesTheMeasuredCause:
    def _run(self, root: Path) -> dict[str, str]:
        fut = root / "data/moat/fut/BTCUSDT"
        fut.mkdir(parents=True)
        (fut / "old.jsonl.gz").write_bytes(b"x")            # stale: 0 symbols written in 30min
        import os
        os.utime(fut / "old.jsonl.gz", (0, 0))
        defects: list[tuple[str, str]] = []
        max_audit.check_self_application(defects)
        return dict(defects)

    def test_a_real_stall_still_fires_the_original_defect(self, fake_root: Path) -> None:
        found = self._run(fake_root)
        assert "recorder-scope-shrank" in found
        assert "recorder stalled" in found["recorder-scope-shrank"]

    def test_a_disk_pause_points_at_the_disk_not_the_recorder(self, fake_root: Path) -> None:
        (fake_root / "data/recorder_heartbeat").write_text("2026-08-20T08:00:41+00:00 DISK-PAUSED")
        found = self._run(fake_root)
        assert "recorder-scope-shrank" not in found, "must not assert a cause it did not measure"
        assert "DISK is the defect" in found["recorder-disk-paused"]

    def test_the_kill_switch_clears_it__the_ACCEPT_path_is_no_longer_welded(
            self, fake_root: Path) -> None:
        """Touching data/RECORDERS_OFF is how the principal ACCEPTS the retirement (R0717)."""
        (fake_root / "data/RECORDERS_OFF").write_text("")
        found = self._run(fake_root)
        assert "recorder-scope-shrank" not in found
        assert "recorder-disk-paused" not in found
