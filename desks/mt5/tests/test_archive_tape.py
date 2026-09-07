"""The tape archiver never deletes a partition it has not proved arrived intact.

The tick tape is the desk's only irreplaceable dataset -- broker-native ticks nobody else holds,
and a tick that was not recorded cannot be bought back. `reclaim_disk` refuses to touch it at any
threshold, which is correct and is also why the box cannot be un-stuck by deletion: measured
2026-09-07, C: at 0.1 GB free with a 5.664 GB tape on it. Moving it is the only honest answer, and
a mover that can lose a partition is worse than a full disk.

So the properties tested here are the ones that make the move safe rather than merely convenient:
a copy is verified before its source goes, a failed verify keeps the source, an interrupted run
resumes instead of re-shipping, retention is measured from the FILENAME (mtime lies -- the tape is
appended by read-concat-rewrite), and the retention floor cannot be set below what the readers
open.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

DESK = pathlib.Path(__file__).resolve().parents[1]


def _module(tmp_path: pathlib.Path):
    """Load archive_tape with its BASE pointed at a throwaway desk."""
    spec = importlib.util.spec_from_file_location(
        "archive_tape_under_test", DESK / "scripts" / "archive_tape.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.BASE = tmp_path
    mod.TAPE = tmp_path / "data" / "tape"
    mod.TICKS = mod.TAPE / "ticks"
    mod.MANIFEST = mod.TAPE / "ARCHIVE_MANIFEST.jsonl"
    mod.REPORT = tmp_path / "reports" / "TAPE_ARCHIVE.json"
    mod.TICKS.mkdir(parents=True)
    return mod


def _partition(mod, symbol: str, day: date, rows: int = 10) -> pathlib.Path:
    d = mod.TICKS / symbol
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{day.isoformat()}.parquet"
    ts = pd.date_range(datetime(day.year, day.month, day.day, tzinfo=UTC), periods=rows, freq="s")
    pd.DataFrame({"ts": ts, "bid": [1.0] * rows, "ask": [1.1] * rows}).to_parquet(p, index=False)
    return p


def test_old_partitions_move_and_recent_ones_do_not(tmp_path) -> None:
    mod = _module(tmp_path)
    today = datetime.now(UTC).date()
    old = _partition(mod, "XAUUSD", today - timedelta(days=120))
    recent = _partition(mod, "XAUUSD", today - timedelta(days=3))
    dest = tmp_path / "archive"

    rc = mod.main(["--dest", str(dest), "--apply"])

    assert rc == 0
    assert not old.exists(), "an archived partition must leave the box"
    assert recent.exists(), "a partition inside the retention window must never move"
    moved = dest / "XAUUSD" / old.name
    assert moved.is_file(), "the partition is not at its destination"
    assert len(pd.read_parquet(moved)) == 10, "the archived copy lost rows"


def test_the_source_survives_a_copy_that_does_not_verify(tmp_path, monkeypatch) -> None:
    """THE ONE THAT MATTERS. A corrupted copy must cost a failure, never the only original."""
    mod = _module(tmp_path)
    src = _partition(mod, "EURUSD", datetime.now(UTC).date() - timedelta(days=99))
    dest = tmp_path / "archive"

    real = mod._digest
    calls = {"n": 0}

    def flaky(path):
        # First call digests the SOURCE, the second the landed copy: differ them so the
        # post-copy comparison fails exactly the way a torn write would.
        calls["n"] += 1
        return real(path) if calls["n"] == 1 else "0" * 64

    monkeypatch.setattr(mod, "_digest", flaky)
    rc = mod.main(["--dest", str(dest), "--apply"])

    assert rc == 1, "a failed verify must be reported as a failure"
    assert src.exists(), "the source was deleted after a copy that did not verify"
    assert not (dest / "EURUSD" / src.name).exists(), "the bad copy was left behind"


def test_an_interrupted_run_resumes_instead_of_reshipping(tmp_path) -> None:
    mod = _module(tmp_path)
    day = datetime.now(UTC).date() - timedelta(days=80)
    src = _partition(mod, "GBPUSD", day)
    dest = tmp_path / "archive"
    (dest / "GBPUSD").mkdir(parents=True)
    # Simulate a crash after the copy landed and before the source was removed.
    (dest / "GBPUSD" / src.name).write_bytes(src.read_bytes())

    assert mod.main(["--dest", str(dest), "--apply"]) == 0
    assert not src.exists(), "a partition already verified at the destination must be cleared"


def test_retention_is_measured_from_the_filename_not_mtime(tmp_path) -> None:
    """The tape is rewritten in place on append, so mtime is today for old ticks."""
    mod = _module(tmp_path)
    old = _partition(mod, "USDJPY", datetime.now(UTC).date() - timedelta(days=200))
    import os
    os.utime(old, None)                      # touch it: mtime is now, contents are 200 days old

    rows, _ = mod.candidates(keep_days=45)

    assert [r["symbol"] for r in rows] == ["USDJPY"], (
        "a freshly-touched old partition was skipped -- retention is reading mtime")


def test_an_undateable_partition_is_never_archived(tmp_path) -> None:
    mod = _module(tmp_path)
    _partition(mod, "XAUUSD", datetime.now(UTC).date() - timedelta(days=90))
    odd = mod.TICKS / "XAUUSD" / "backup-old.parquet"
    odd.write_bytes(b"not a date")

    rows, skipped = mod.candidates(keep_days=45)

    assert skipped["undateable"] == 1
    assert all(r["path"] != odd for r in rows), "a file whose day cannot be read was queued"
    assert odd.exists()


def test_retention_cannot_be_set_below_what_the_readers_open(tmp_path) -> None:
    mod = _module(tmp_path)
    _partition(mod, "XAUUSD", datetime.now(UTC).date() - timedelta(days=90))
    assert mod.main(["--dest", str(tmp_path / "a"), "--keep-days", "20", "--apply"]) == 2, (
        "orthogonal_sweep and edge_search read the last 30 files; a 20-day retention would ship "
        "away partitions a live reader was going to open")


def test_a_destination_inside_the_tape_is_refused(tmp_path) -> None:
    mod = _module(tmp_path)
    _partition(mod, "XAUUSD", datetime.now(UTC).date() - timedelta(days=90))
    assert mod.main(["--dest", str(mod.TAPE / "archive"), "--apply"]) == 2, (
        "a destination inside the tape would copy a file onto itself and then delete the source")


def test_the_manifest_records_every_move(tmp_path) -> None:
    mod = _module(tmp_path)
    day = datetime.now(UTC).date() - timedelta(days=70)
    _partition(mod, "XAUUSD", day)
    dest = tmp_path / "archive"

    mod.main(["--dest", str(dest), "--apply"])

    rows = [json.loads(x) for x in mod.MANIFEST.read_text("utf-8").splitlines() if x.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "XAUUSD" and row["day"] == day.isoformat()
    assert row["rows"] == 10 and len(row["sha256"]) == 64
    assert mod.verify(dest)["verified"] == 1, "the archive does not verify against its manifest"


def test_verify_reports_a_partition_that_vanished_from_the_archive(tmp_path) -> None:
    """The manifest exists so a lost archive is LOUD rather than discovered years later."""
    mod = _module(tmp_path)
    day = datetime.now(UTC).date() - timedelta(days=70)
    _partition(mod, "XAUUSD", day)
    dest = tmp_path / "archive"
    mod.main(["--dest", str(dest), "--apply"])

    (dest / "XAUUSD" / f"{day.isoformat()}.parquet").unlink()

    result = mod.verify(dest)
    assert result["missing_count"] == 1 and result["verified"] == 0


def test_measure_only_is_the_default(tmp_path) -> None:
    mod = _module(tmp_path)
    src = _partition(mod, "XAUUSD", datetime.now(UTC).date() - timedelta(days=90))
    dest = tmp_path / "archive"

    assert mod.main(["--dest", str(dest)]) == 0
    assert src.exists(), "a run without --apply moved a file"
    assert not dest.exists() or not any(dest.rglob("*.parquet"))


def test_a_destination_too_small_for_the_batch_is_refused(tmp_path, monkeypatch) -> None:
    mod = _module(tmp_path)
    src = _partition(mod, "XAUUSD", datetime.now(UTC).date() - timedelta(days=90))
    dest = tmp_path / "archive"
    monkeypatch.setattr(mod, "_free_bytes", lambda p: 10)

    assert mod.main(["--dest", str(dest), "--apply"]) == 2
    assert src.exists(), "a batch that cannot fit must not be started at all"
