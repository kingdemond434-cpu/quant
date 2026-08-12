"""Desk state: provenance is not freshness, and a snapshot must never read as current.

The bug these tests exist to prevent was written into the first draft of the module itself --
fresh_enough() returned True for any LIVE file regardless of age. On the box where it was written,
23 of 27 artifacts were LIVE and over 48h old, one of them 12.5 days.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from libs.ops.desk_state import SYNC_SET, State, coverage, read, syncable


def _write(root: Path, rel: str, payload: dict, *, age_h: float = 0.0) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), "utf-8")
    if age_h:
        old = time.time() - age_h * 3600
        os.utime(p, (old, old))
    return p


# ------------------------------------------------------------------ the load-bearing property
def test_live_is_provenance_not_freshness(tmp_path: Path) -> None:
    """THE BUG THIS MODULE SHIPPED AND THEN FIXED. A file in data/ means something produced it
    here ONCE. Whether that was an hour ago or a fortnight ago is the entire question."""
    _write(tmp_path, "data/promotion_queue.json", {"x": 1}, age_h=300)
    s = read("promotion_queue.json", root=tmp_path)
    assert s.source == "LIVE" and s.source_age_h > 290
    assert not s.fresh_enough(24), "a 12-day-old LIVE file is not fresh"
    assert s.fresh_enough(400), "and the caller's own tolerance decides"


def test_a_recent_live_file_is_fresh(tmp_path: Path) -> None:
    _write(tmp_path, "data/organ_liveness.json", {"x": 1}, age_h=1)
    assert read("organ_liveness.json", root=tmp_path).fresh_enough(24)


def test_unknown_age_is_never_fresh() -> None:
    assert not State("x", "SNAPSHOT", {}, None).fresh_enough(999_999)


def test_absent_is_unmeasured_never_zero(tmp_path: Path) -> None:
    s = read("promotion_queue.json", root=tmp_path)
    assert s.source == "ABSENT" and s.payload is None
    assert "UNMEASURED, never zero" in s.why and not s.usable


# ------------------------------------------------------------------ snapshot honesty
def test_a_snapshot_carries_the_source_age_not_the_checkout_age(tmp_path: Path) -> None:
    """THE TRAP. A clone is seconds old and the numbers inside it may be days old. Reporting the
    clone's age would make every stale mirror look current."""
    _write(tmp_path, "docs/state/backup_status.json", {"x": 1})
    (tmp_path / "docs/state/MANIFEST.json").write_text(json.dumps({
        "files": {"backup_status.json": {"source_age_h_at_sync": 100.0,
                                         "synced_utc": "2026-08-12T00:00:00+00:00"}}}), "utf-8")
    s = read("backup_status.json", root=tmp_path)
    assert s.source == "SNAPSHOT"
    assert s.source_age_h >= 100.0, "the VPS source age must survive the trip"
    assert not s.fresh_enough(24)


def test_live_wins_over_snapshot(tmp_path: Path) -> None:
    _write(tmp_path, "docs/state/cost_hunt.json", {"which": "snapshot"})
    _write(tmp_path, "data/cost_hunt.json", {"which": "live"})
    assert read("cost_hunt.json", root=tmp_path).payload["which"] == "live"


def test_a_snapshot_with_no_manifest_entry_has_unknown_age_and_is_not_fresh(tmp_path) -> None:
    _write(tmp_path, "docs/state/fence_yield.json", {"x": 1})
    s = read("fence_yield.json", root=tmp_path)
    assert s.source == "SNAPSHOT" and s.source_age_h is None and not s.fresh_enough(1e9)


def test_an_empty_live_file_is_not_treated_as_data(tmp_path: Path) -> None:
    p = tmp_path / "data/utilisation.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    assert read("utilisation.json", root=tmp_path).source == "ABSENT"


# ------------------------------------------------------------------ what must never be mirrored
def test_credentials_and_the_moat_tape_are_never_syncable() -> None:
    """A repo is not a place for credentials or a 10GB depth tape."""
    for bad in ("secrets/binance.json", "moat/execution_tape", "lake/ohlcv.parquet",
                "sor_research.sqlite"):
        assert not syncable(bad), bad


def test_only_declared_artifacts_sync() -> None:
    assert syncable("promotion_queue.json")
    assert not syncable("some_random_file.json")


def test_jsonl_artifacts_parse_to_rows(tmp_path: Path) -> None:
    p = tmp_path / "data/miner_yield.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"a":1}\n\n{"a":2}\nnot json\n', "utf-8")
    assert read("miner_yield.jsonl", root=tmp_path).payload == [{"a": 1}, {"a": 2}]


# ------------------------------------------------------------------ the honest denominator
def test_coverage_reports_what_this_box_can_actually_see(tmp_path: Path) -> None:
    _write(tmp_path, "data/promotion_queue.json", {"x": 1})
    c = coverage(root=tmp_path)
    assert c["n_artifacts"] == len(SYNC_SET) and c["live"] == 1
    assert c["absent"] == len(SYNC_SET) - 1
    assert "describes this box, not the desk" in c["why"]
