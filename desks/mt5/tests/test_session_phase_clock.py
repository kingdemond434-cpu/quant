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


# THE STAMP BASIS (audit HOLD 2026-11-11). The desk's ledgers carry broker STAMPS, labelled
# "+00:00" by h1_source (a label, not a conversion) or declared `broker_deal_epoch` by the live
# ledger. A stamp's hour is its phase hour; only a row declaring a true-UTC basis is offset.
#: A real shadow-ledger row, as shadow_forward writes it (str(t.entry_time) + bars.stamp()).
SHADOW_ROW = {"entry_time": "2026-08-18 08:00:00+00:00", "exit_time": "2026-08-18 13:00:00+00:00",
              "side": 1, "entry": 1.10012, "exit": 1.10161, "r_multiple": 1.25,
              "reason": "time", "phase": "forward", "bar_source": "MT5:FusionMarkets-Live",
              "evidence_venue": "fusion", "bars_fetched_utc": "2026-08-18T14:02:11+00:00",
              "bars_freshest": "2026-08-18T13:00:00+00:00", "bars_stale": False,
              "promotion_authority": True, "h1_source_version": 3}
#: A real live-ledger row's clock fields (gold_asia places at 07:00 broker).
LIVE_ROW = {"entry_time": "2026-10-30T07:41:52.496000+00:00", "r_multiple": 0.2543,
            "timestamp_basis": "broker_deal_epoch", "sleeve": "gold_asia"}


def test_ledger_rows_are_broker_stamps_unless_they_declare_utc() -> None:
    assert sp.row_basis(SHADOW_ROW) == "broker"
    assert sp.row_basis(LIVE_ROW) == "broker"
    assert sp.row_basis({"entry_time": "x", "timestamp_basis": "utc"}) == "utc"


def test_a_real_shadow_ledger_row_keeps_its_stamp_hours_phase_in_every_season() -> None:
    for month in (1, 7):
        row = dict(SHADOW_ROW, entry_time=f"2026-{month:02d}-15 08:00:00+00:00")
        got = sp.returns_in_phase([row], sp.phase_for_hour(8), broker_utc_offset_h=None)
        assert got.tolist() == [1.25], f"stamp 08:00 must stay phase(8) in month {month}"
    live = sp.returns_in_phase([LIVE_ROW], sp.phase_for_hour(7), broker_utc_offset_h=None)
    assert live.tolist() == [0.2543], "gold_asia's 07:41 stamp is the 07:00 phase, not 10:00"


def test_state_admission_labels_a_stamp_on_its_own_hour() -> None:
    fn = sa.build_labeller("session")
    assert fn is not None
    for when in ("2026-07-01T08:00:00+00:00", "2026-01-15T08:00:00+00:00"):
        assert fn(sa.Trade(sleeve="s", when=when, r=0.0)) == sp.phase_for_hour(8)


def test_state_admission_offsets_a_declared_utc_instant_on_the_clock_in_force_then() -> None:
    fn = sa.build_labeller("session")
    assert fn is not None
    summer = sa.Trade(sleeve="s", when="2026-07-01T05:00:00+00:00", r=0.0, basis="utc")
    winter = sa.Trade(sleeve="s", when="2026-01-15T06:00:00+00:00", r=0.0, basis="utc")
    # Both are stamp 08:00 on the venue clock: the same phase, though an hour apart in UTC.
    assert fn(summer) == fn(winter) == sp.phase_for_hour(8)


def test_declared_utc_rows_are_labelled_on_the_clock_in_force_at_their_own_entry() -> None:
    rows = [{"entry_time": "2026-07-01T05:00:00+00:00", "r_multiple": 1.0,
             "timestamp_basis": "utc"},
            {"entry_time": "2026-01-15T06:00:00+00:00", "r_multiple": 2.0,
             "timestamp_basis": "utc"}]
    got = sp.returns_in_phase(rows, sp.phase_for_hour(8), broker_utc_offset_h=None)
    assert sorted(got.tolist()) == [1.0, 2.0]
    # One offset for both (today's +3) mislabels the January trade.
    one = sp.returns_in_phase(rows, sp.phase_for_hour(8), broker_utc_offset_h=3)
    assert one.tolist() == [1.0]


@pytest.mark.parametrize(("at", "off"), [
    # The autumn split week: Europe left summer time on 2026-10-25, New York on 2026-11-01. The
    # venue follows New York, so it is still +3 midweek and +2 from the Monday after.
    (datetime(2026, 10, 28, 12, tzinfo=UTC), 3), (datetime(2026, 10, 31, 20, tzinfo=UTC), 3),
    (datetime(2026, 11, 2, 1, tzinfo=UTC), 2),
])
def test_the_autumn_split_week_follows_new_york(at, off) -> None:
    assert sp.broker_utc_offset_h(at=at) == (off, "venue_clock_ny_plus_7")


def test_now_is_offset_but_history_is_not() -> None:
    # The allocator's CURRENT phase is a true UTC instant: 05:00 UTC in July is stamp 08:00.
    at = datetime(2026, 7, 1, 5, tzinfo=UTC)
    off, _ = sp.broker_utc_offset_h(at=at)
    assert sp.phase_at(at, broker_utc_offset_h=off) == sp.phase_for_hour(8)


def test_a_naive_broker_stamp_converts_on_its_own_dates_clock() -> None:
    assert sp.stamp_to_utc(datetime.fromisoformat("2026-07-01T08:00:00")).hour == 5
    assert sp.stamp_to_utc(datetime.fromisoformat("2026-01-15T08:00:00")).hour == 6


def test_the_allocator_reads_trade_hours_on_each_trades_own_clock() -> None:
    import pf_allocator as pa
    # naive and "+00:00"-labelled stamps alike are broker stamps; a declared UTC row is not moved
    rows = {"s": [{"entry_time": "2026-07-01T08:00:00"},
                  {"entry_time": "2026-01-15 08:00:00+00:00"},
                  {"entry_time": "2026-03-02T11:00:00+00:00", "timestamp_basis": "utc"}]}
    assert pa._trade_hours("s", rows, 3) == (5, 6, 11)
    src = Path(pa.__file__).read_text("utf-8")
    assert "returns_in_phase(rows, phase, broker_utc_offset_h=None)" in src
    # The admitted-extra-dimensions branch reads the same per-trade clock as the main path.
    assert "returns_in_phase(keep, phase, broker_utc_offset_h=None)" in src
    assert "broker_utc_offset_h=broker_utc_offset_h)" not in src


def test_state_admission_run_carries_each_rows_declared_basis(tmp_path, monkeypatch) -> None:
    import state_admission_run as sar
    d = tmp_path / "shadow"
    d.mkdir()
    (d / "ledger_s.json").write_text(
        '[{"entry_time": "2026-07-01 08:00:00+00:00", "r_multiple": 1.0},'
        ' {"entry_time": "2026-07-01T05:00:00+00:00", "r_multiple": 2.0,'
        ' "timestamp_basis": "utc"}]', "utf-8")
    monkeypatch.setattr(sar, "LEDGER_DIRS", (d,))
    got = {t.r: t.basis for t in sar.load_trades("shadow")}
    assert got == {1.0: "broker", 2.0: "utc"}
