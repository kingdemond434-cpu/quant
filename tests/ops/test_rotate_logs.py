"""ops/rotate_logs.py: a rotation archives the WHOLE log, verified, and never discards history."""

from __future__ import annotations

import gzip
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("rotate_logs", ROOT / "ops" / "rotate_logs.py")
assert _spec and _spec.loader
R = importlib.util.module_from_spec(_spec)
sys.modules["rotate_logs"] = R
_spec.loader.exec_module(R)

NOW = datetime(2026, 11, 13, 23, 0, tzinfo=UTC)


def _log(tmp_path: Path, n: int) -> Path:
    p = tmp_path / "g.log"
    p.write_bytes(b"".join(b"line %07d\n" % i for i in range(n)))
    return p


def test_small_log_is_left_alone(tmp_path: Path) -> None:
    p = _log(tmp_path, 10)
    assert R.rotate(p, max_bytes=10_000, now=NOW) == "small"
    assert p.exists() and not (tmp_path / "archive").exists()


def test_rotation_keeps_every_byte_in_the_archive(tmp_path: Path) -> None:
    p = _log(tmp_path, 5000)
    original = p.read_bytes()
    assert R.rotate(p, max_bytes=100, now=NOW) == "rotated"
    archives = list((tmp_path / "archive").glob("g.log.*.gz"))
    assert len(archives) == 1
    assert gzip.decompress(archives[0].read_bytes()) == original
    assert not p.exists() and not (tmp_path / "g.log.rotating").exists()


def test_a_second_rotation_never_replaces_the_first(tmp_path: Path) -> None:
    p = _log(tmp_path, 5000)
    first = p.read_bytes()
    R.rotate(p, max_bytes=100, now=NOW)
    p.write_bytes(b"second\n" * 1000)
    R.rotate(p, max_bytes=100, now=NOW)  # same second: must get a new name
    got = sorted(gzip.decompress(a.read_bytes()) for a in (tmp_path / "archive").glob("*.gz"))
    assert got == sorted([first, b"second\n" * 1000])


def test_a_leftover_staging_file_is_archived_first(tmp_path: Path) -> None:
    staging = tmp_path / "g.log.rotating"
    staging.write_bytes(b"interrupted\n")
    (tmp_path / "g.log").write_bytes(b"x\n")
    assert R.rotate(tmp_path / "g.log", max_bytes=10_000, now=NOW) == "small"
    assert not staging.exists()
    [a] = (tmp_path / "archive").glob("*.gz")
    assert gzip.decompress(a.read_bytes()) == b"interrupted\n"


def test_a_failed_archive_keeps_the_staging_copy_and_exits_nonzero(
    tmp_path: Path, monkeypatch
) -> None:
    p = _log(tmp_path, 5000)
    original = p.read_bytes()

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(R, "archive", boom)
    assert R.rotate(p, max_bytes=100, now=NOW) == "stuck"
    assert (tmp_path / "g.log.rotating").read_bytes() == original
    assert R.main(["--max-mb", "0", "--dir", str(tmp_path)]) == 2


def test_the_task_is_declared_with_an_ifmissing_installer() -> None:
    man = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text("utf-8")
    assert 'TASK name="MT5-RotateLogs"' in man and 'runs="ops/rotate_logs.py"' in man
    inst = (ROOT / "desks" / "mt5" / "scripts" / "install_rotate_logs_task.ps1").read_text("utf-8")
    assert "[switch]$IfMissing" in inst and "'SYSTEM'" in inst
    assert "MT5-RotateLogs.txt" in inst  # its own output is never a *.log it would rotate
