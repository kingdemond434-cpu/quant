"""A COVERED STORE THAT OUTGROWS THE OFF-BOX ROUTE MUST GO LOUD (gap-fixer 2026-08-26).

sor_research entered _STORES at 487KB (2026-08-01) and grew 1300x to 637MB; the backup kept
bundling it and GitHub's pre-receive rejected the push -- a replica that LOOKED covered and
could never leave the box. Pins: an over-cap covered store reports OVERSIZED and degrades the
verdict (never a silent giant bundle, never OK); an under-cap store replicates as before.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_moat_backup as mb


@pytest.fixture()
def scratch(tmp_path: Path, monkeypatch) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "capital_events.jsonl").write_text('{"e": 1}\n')
    monkeypatch.setattr(mb, "_STORES", {
        "capital_events": ("data/capital_events.jsonl", "file"),
    })
    monkeypatch.setattr(mb, "_NOT_COVERED", ())
    return tmp_path


def test_over_cap_store_is_oversized_and_degrades(scratch: Path, monkeypatch) -> None:
    monkeypatch.setattr(mb, "_COVERED_MAX_BYTES", 4)  # the 6-byte store is now over cap
    rep = mb.build_backup(scratch, dest=scratch / "backups/moat", free_pct=50.0)
    assert rep["stores"]["capital_events"]["status"] == "OVERSIZED"
    assert rep["oversized_stores"] == ["capital_events"]
    assert rep["status"] == "DEGRADED"
    assert not (scratch / "backups/moat/capital_events").exists()  # no bundle written


def test_under_cap_store_replicates(scratch: Path) -> None:
    rep = mb.build_backup(scratch, dest=scratch / "backups/moat", free_pct=50.0)
    assert rep["stores"]["capital_events"]["status"] == "REPLICATED"
    assert rep["status"] == "OK"
