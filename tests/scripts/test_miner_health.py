"""A dead miner must never read as a healthy one.

REGRESSION FOR 2026-08-26. `scripts/build_research_facts.py` measured miner health as
`fetch_errors / rows`, which reported 35 of 41 sources healthy while 30 had produced zero
usable rows for 18 consecutive hourly sweeps. Every blind spot failed toward a CLEAN verdict,
which is the one direction nothing downstream catches, and organs are under standing orders to
trust that file without recomputing it.

These are written against the failure SHAPES, not against the six source names that happened to
be broken that day -- a test pinned to `collective2` would pass forever once that one source was
fixed, while the shape it belongs to went on being invisible.

`classify_row` is the single definition of a usable row, imported by BOTH the fence and the
facts-pack builder, so the classifier tests below guard the pack's numbers as well as the
fence's verdict. That sharing is the point: the previous bug was possible because "is this row
information?" was answered in one place and never asked in the other.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.check_miner_health import classify_row, scan  # noqa: E402


def _write_sweep(src: Path, idx: int, rows: list[dict]) -> None:
    src.mkdir(parents=True, exist_ok=True)
    (src / f"discoveries_2026082{idx // 10}_{idx % 10:02d}00.json").write_text(
        json.dumps(rows), "utf-8")


@pytest.fixture
def intel(tmp_path, monkeypatch):
    """An intelligence tree the scanner reads, isolated from the real archives."""
    base = tmp_path / "intelligence"
    base.mkdir()
    monkeypatch.setattr("scripts.check_miner_health.INTEL", base)
    return base


def test_a_miner_emitting_only_selector_stubs_is_not_healthy(intel):
    """THE STUB TRAP: 'page shape drifted' is a row, and it is not information.

    This is the shape that hid fbs_tape (21 rows, 21 stubs) behind error_rate 0.0.
    """
    for i in range(8):
        _write_sweep(intel / "stubby", i, [{"kind": "raw_capture",
                                            "title": "page shape drifted",
                                            "needs_selector_work": True}])
    report = scan(streak=6, days=3650)
    assert report["stubby"]["real_rows_recent"] == 0
    assert report["stubby"]["dark_streak"] >= 6, "a stub-only miner must read as dark"


def test_a_miner_emitting_nothing_at_all_is_reported_not_omitted(intel):
    """THE OMISSION TRAP: zero rows used to drop the source from the pack entirely.

    The most completely broken miners were therefore the most invisible ones.
    """
    for i in range(8):
        _write_sweep(intel / "silent", i, [])
    report = scan(streak=6, days=3650)
    assert "silent" in report, "a source producing nothing must still appear"
    assert report["silent"]["dark_streak"] >= 6


def test_error_rows_never_count_as_output(intel):
    for i in range(8):
        _write_sweep(intel / "erroring", i,
                     [{"kind": "fetch_error", "title": "403 Client Error"}])
    report = scan(streak=6, days=3650)
    assert report["erroring"]["real_rows_recent"] == 0
    assert "403" in report["erroring"]["last_error"]


def test_one_real_row_clears_the_dark_streak(intel):
    """The positive control: a fence that never passes a healthy miner is not a fence."""
    for i in range(6):
        _write_sweep(intel / "working", i, [{"kind": "fetch_error", "title": "blip"}])
    _write_sweep(intel / "working", 6, [{"kind": "track_record", "title": "a real find"}])
    report = scan(streak=6, days=3650)
    assert report["working"]["dark_streak"] == 0
    assert report["working"]["real_rows_recent"] == 1


def test_a_walled_source_is_dispositioned_not_defective(intel, monkeypatch):
    """A recorded §13 wall is a decision, not a silent failure -- it must not page forever."""
    monkeypatch.setattr("scripts.check_miner_health._walled",
                        lambda: {"blocked": {"verdict": "ROBOTS_DISALLOW"}})
    for i in range(8):
        _write_sweep(intel / "blocked", i,
                     [{"kind": "walled", "title": "ROBOTS_DISALLOW"}])
    report = scan(streak=6, days=3650)
    assert report["blocked"]["walled"] is True
    assert report["blocked"]["verdict"] == "ROBOTS_DISALLOW"


class TestClassifyRow:
    """The shared classifier -- these assertions bind the facts pack too.

    Each case is a row shape that scored as healthy under `fetch_errors / rows`.
    """

    def test_selector_stub_is_not_real(self):
        assert classify_row({"kind": "raw_capture", "needs_selector_work": True}) == "stub"

    def test_fetch_error_is_not_real(self):
        assert classify_row({"kind": "fetch_error"}) == "error"

    def test_any_kind_ending_in_error_is_an_error(self):
        assert classify_row({"kind": "parse_error"}) == "error"

    def test_recorded_wall_is_its_own_bucket(self):
        assert classify_row({"kind": "walled", "verdict": "ROBOTS_DISALLOW"}) == "walled"

    def test_a_genuine_discovery_is_real(self):
        assert classify_row({"kind": "track_record", "title": "a find"}) == "real"

    def test_a_non_dict_is_never_counted_as_information(self):
        assert classify_row("not a row") == "stub"
