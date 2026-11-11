"""L3 (2026-10-13): gateway_state.json's placement_pass is broker time under a UTC label.

At 15:20 UTC it read 18:20 "+00:00". Every reader now goes through one converter: a stamp marked
`placement_pass_clock: "utc"` is taken as written, a legacy stamp is the venue clock (New York
wall time + 7 h) converted with its DST dates, and an unreadable stamp is UNMEASURED (None).
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import gateway_clock as gc

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "desks" / "mt5" / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))

UTC_NOW = datetime(2026, 10, 13, 15, 20, tzinfo=UTC)
BROKER_STAMP = "2026-10-13T18:20:00+00:00"   # what the gateway writes at 15:20 UTC, EEST


def test_a_legacy_broker_stamp_is_three_hours_ahead_in_october() -> None:
    assert gc.placement_pass_utc({"placement_pass": BROKER_STAMP}) == UTC_NOW


@pytest.mark.parametrize(("stamp", "utc"), [
    # New York changes clocks on 2026-11-01, a week AFTER Europe (10-25): the venue follows NY.
    ("2026-10-28T18:20:00+00:00", "2026-10-28T15:20:00+00:00"),   # EU winter, NY summer: +3
    ("2026-11-03T18:20:00+00:00", "2026-11-03T16:20:00+00:00"),   # both winter: +2
    ("2026-01-15T09:00:00+00:00", "2026-01-15T07:00:00+00:00"),
    ("2026-07-15T09:00:00+00:00", "2026-07-15T06:00:00+00:00"),
])
def test_the_offset_follows_new_york_daylight_time(stamp: str, utc: str) -> None:
    got = gc.placement_pass_utc({"placement_pass": stamp})
    assert got == datetime.fromisoformat(utc)


def test_the_converter_does_not_lean_on_the_zero_offset_resolver(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import session_phase  # type: ignore[import-not-found]
    # the audit found this resolver answering 0 on every host; the converter must not care
    monkeypatch.setattr(session_phase, "broker_utc_offset_h", lambda: (0, "pinned"))
    assert gc.placement_pass_utc({"placement_pass": BROKER_STAMP}) == UTC_NOW


def test_a_stamp_marked_utc_is_taken_as_written() -> None:
    doc = {"placement_pass": "2026-10-13T15:20:00+00:00", "placement_pass_clock": "utc"}
    assert gc.placement_pass_utc(doc) == UTC_NOW


def test_a_stamp_with_a_real_offset_is_not_shifted_twice() -> None:
    # audit of #328: "+03:00" is already an honest instant; only the "+00:00" label is suspect
    assert gc.placement_pass_utc({"placement_pass": "2026-10-13T18:20:00+03:00"}) == UTC_NOW


@pytest.mark.parametrize("doc", [None, {}, {"placement_pass": "not a time"}, []])
def test_absent_or_unreadable_is_none(doc: object) -> None:
    assert gc.placement_pass_utc(doc) is None


def test_live_system_state_reports_the_utc_age(monkeypatch: pytest.MonkeyPatch) -> None:
    import live_system_state as lss  # type: ignore[import-not-found]
    out = lss._execution_section({"placement_pass": BROKER_STAMP}, None,
                                 UTC_NOW + timedelta(hours=2))
    assert out["last_pass_at"] == "2026-10-13T15:20:00+00:00"
    assert out["last_pass_age_h"] == 2.0          # was -1.0: three hours too young
