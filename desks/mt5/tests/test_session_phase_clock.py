"""Session phases read the venue's clock, New York + 7 h, at the instant asked about (2026-09-30).

The "live terminal" tier read `h1_source.broker_utc_offset_hours`, which returns 0.0 by
construction, and recorded that 0 into broker_clock.json on 2026-09-11. Every phase the allocator
and state admission computed since was three hours off in summer.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_phase as sp  # noqa: E402

from libs.regime import state_admission as sa  # noqa: E402


@pytest.mark.parametrize(("at", "off"), [
    (datetime(2026, 7, 1, 12, tzinfo=UTC), 3), (datetime(2026, 1, 15, 12, tzinfo=UTC), 2),
    (datetime(2026, 3, 16, 12, tzinfo=UTC), 3), (datetime(2026, 11, 2, 12, tzinfo=UTC), 2),
])
def test_the_offset_is_the_venue_clock_at_that_instant(at, off) -> None:
    assert sp.broker_utc_offset_h(at=at) == (off, "venue_clock_ny_plus_7")


def test_a_recorded_zero_no_longer_decides_the_clock(tmp_path, monkeypatch) -> None:
    rec = tmp_path / "broker_clock.json"
    rec.write_text('{"utc_offset_hours": 0, "source": "live_terminal"}', "utf-8")
    monkeypatch.setattr(sp, "BROKER_CLOCK", rec)
    off, src = sp.broker_utc_offset_h(at=datetime(2026, 9, 30, 12, tzinfo=UTC))
    assert (off, src) == (3, "venue_clock_ny_plus_7")


def test_one_stamp_hour_is_one_phase_in_both_seasons() -> None:
    # Stamp 08:00 is 05:00 UTC under US daylight time and 06:00 UTC otherwise.
    for at in (datetime(2026, 7, 1, 5, tzinfo=UTC), datetime(2026, 1, 15, 6, tzinfo=UTC)):
        off, _ = sp.broker_utc_offset_h(at=at)
        assert sp.phase_at(at, broker_utc_offset_h=off) == sp.phase_for_hour(8)


def test_state_admission_labels_each_trade_with_the_offset_in_force_then() -> None:
    fn = sa.build_labeller("session")
    assert fn is not None
    summer = sa.Trade(sleeve="s", when="2026-07-01T05:00:00+00:00", r=0.0)
    winter = sa.Trade(sleeve="s", when="2026-01-15T06:00:00+00:00", r=0.0)
    # Both are stamp 08:00 on the venue clock: the same phase, though an hour apart in UTC.
    assert fn(summer) == fn(winter) == sp.phase_for_hour(8)


def test_past_trades_are_labelled_on_the_clock_in_force_at_their_own_entry() -> None:
    # Both are stamp 08:00: 05:00 UTC under US daylight time, 06:00 UTC in January.
    rows = [{"entry_time": "2026-07-01T05:00:00+00:00", "r_multiple": 1.0},
            {"entry_time": "2026-01-15T06:00:00+00:00", "r_multiple": 2.0}]
    got = sp.returns_in_phase(rows, sp.phase_for_hour(8), broker_utc_offset_h=None)
    assert sorted(got.tolist()) == [1.0, 2.0]
    # One offset for both (today's +3) mislabels the January trade.
    one = sp.returns_in_phase(rows, sp.phase_for_hour(8), broker_utc_offset_h=3)
    assert one.tolist() == [1.0]


def test_a_naive_broker_stamp_converts_on_its_own_dates_clock() -> None:
    assert sp.stamp_to_utc(datetime.fromisoformat("2026-07-01T08:00:00")).hour == 5
    assert sp.stamp_to_utc(datetime.fromisoformat("2026-01-15T08:00:00")).hour == 6


def test_the_allocator_reads_trade_hours_on_each_trades_own_clock() -> None:
    import pf_allocator as pa
    rows = {"s": [{"entry_time": "2026-07-01T08:00:00"}, {"entry_time": "2026-01-15T08:00:00"}]}
    assert pa._trade_hours("s", rows, 3) == (5, 6)
    src = Path(pa.__file__).read_text("utf-8")
    assert "returns_in_phase(rows, phase, broker_utc_offset_h=None)" in src
    # The admitted-extra-dimensions branch reads the same per-trade clock as the main path.
    assert "returns_in_phase(keep, phase, broker_utc_offset_h=None)" in src
    assert "broker_utc_offset_h=broker_utc_offset_h)" not in src
