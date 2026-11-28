"""MetaTrader deal and tick epochs are the BROKER's wall clock; the ledgers stamp true UTC.

Row 247/239 (2026-10-29): deal 217155220 (Fusion, gold_asia) closed at 09:09:01 UTC, carries the
epoch of 12:09:01, and was written at 09:09:15 UTC with `exit_time` 12:09:01+00:00 -- three hours
in the future of its own write. What is pinned:

  * that deal round-trips to 09:09:01Z, by the measured offset and by the calendar rule;
  * the offset is read only off a FRESH tick, and the calendar rule follows New York's DST
    (+3 before 2026-11-01, +2 after);
  * a venue without the calendar rule (`calendar=False`) is never guessed;
  * legacy rows are read through `row_utc`, never rewritten, and the RED check fires on a
    converted row whose stamp leads its own write.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.ops import gateway_clock as gc

#: deal 217155220's exit, as the broker stamped it, and the true instant.
EPOCH = datetime(2026, 10, 29, 12, 9, 1, tzinfo=UTC).timestamp()
TRUE_UTC = "2026-10-29T09:09:01+00:00"


def test_deal_217155220_round_trips_to_its_real_utc_close() -> None:
    assert gc.broker_epoch_to_utc(EPOCH, 3) == (TRUE_UTC, gc.BASIS_MEASURED)
    assert gc.broker_epoch_to_utc(EPOCH) == (TRUE_UTC, gc.BASIS_CALENDAR)
    row = {"time": "2026-10-29T09:09:15+00:00", "exit_time": TRUE_UTC,
           "timestamp_basis": gc.BASIS_MEASURED, "deal": 217155220}
    assert gc.ledger_clock_breaches([row]) == []


def test_the_offset_is_read_only_off_a_fresh_tick() -> None:
    wall = datetime(2026, 10, 29, 9, 9, 15, tzinfo=UTC).timestamp()
    assert gc.measured_offset_h(wall + 3 * 3600 + 2, wall) == 3
    assert gc.measured_offset_h(wall + 3 * 3600 - 1800, wall) is None     # 30 min stale
    assert gc.measured_offset_h(None, wall) is None
    assert gc.measured_offset_h(wall + 20 * 3600, wall) is None           # not a venue offset


def test_the_calendar_rule_follows_new_york_dst() -> None:
    after = datetime(2026, 11, 3, 12, 0, tzinfo=UTC).timestamp()           # NY on standard time
    assert gc.broker_epoch_to_utc(after)[0] == "2026-11-03T10:00:00+00:00"


def test_another_venue_is_never_guessed() -> None:
    iso, basis = gc.broker_epoch_to_utc(EPOCH, None, calendar=False)
    assert basis == gc.BASIS_UNMEASURED and iso == "2026-10-29T12:09:01+00:00"
    assert gc.broker_epoch_to_utc(0) == (None, gc.BASIS_UNMEASURED)
    assert gc.broker_epoch_to_utc("x") == (None, gc.BASIS_UNMEASURED)


def test_legacy_rows_are_read_corrected_and_never_rewritten() -> None:
    legacy = {"time": "2026-10-29T09:09:15+00:00", "exit_time": "2026-10-29T12:09:01+00:00",
              "timestamp_basis": "broker_deal_epoch"}
    assert gc.row_utc(legacy, "exit_time") == datetime.fromisoformat(TRUE_UTC)
    assert legacy["exit_time"] == "2026-10-29T12:09:01+00:00"
    assert gc.ledger_clock_breaches([legacy]) == []                       # read via row_utc
    assert gc.row_utc({"exit_time": TRUE_UTC, "timestamp_basis": "mt5_server_epoch"},
                      "exit_time") is None                                # unknown: not guessed


def test_a_converted_row_whose_stamp_leads_its_write_is_red() -> None:
    wrote = datetime(2026, 10, 29, 9, 9, 15, tzinfo=UTC)
    bad = {"time": wrote.isoformat(), "deal": 1, "timestamp_basis": gc.BASIS_CALENDAR,
           "exit_time": (wrote + timedelta(hours=3)).isoformat()}
    late = {**bad, "exit_time": (wrote - timedelta(hours=5)).isoformat()}  # recorded late: fine
    assert len(gc.ledger_clock_breaches([bad])) == 1
    assert gc.ledger_clock_breaches([late]) == []


def test_ftmo_fills_convert_only_on_a_measured_offset() -> None:
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    for p in (str(desk), str(desk.parent.parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from prop import ftmo_follower as F

    base = {"symbol": F.SYMBOL, "position_id": 9, "commission": 0.0, "fee": 0.0, "swap": 0.0,
            "volume": 0.01, "order": 5, "profit": 1.0, "reason": 4}
    entry = SimpleNamespace(**base, magic=F.MAGIC, entry=0, type=0, price=4000.0,
                            time=EPOCH - 3600)
    exit_ = SimpleNamespace(**base, magic=F.MAGIC, entry=1, type=1, price=4001.0, time=EPOCH)
    order = SimpleNamespace(ticket=5, sl=3990.0, tp=4020.0, price_open=4000.0)
    rows = F.compose_fills([entry, exit_], [order], set(), account_key="k", contract=100.0,
                           recorded_at="2026-10-29T09:09:15+00:00", offset_h=3)
    assert rows[0]["exit_time"] == TRUE_UTC and rows[0]["timestamp_basis"] == gc.BASIS_MEASURED
    raw = F.compose_fills([entry, exit_], [order], set(), account_key="k", contract=100.0,
                          recorded_at="2026-10-29T09:09:15+00:00")
    assert raw[0]["timestamp_basis"] == gc.BASIS_UNMEASURED           # unmeasured: not guessed
    assert raw[0]["exit_time"] == "2026-10-29T12:09:01+00:00"


# ---------------------------------------------------------------- audit of #518: the offset regime
#: US daylight time starts Sunday 2027-03-14: New York is UTC-5 before it, UTC-4 after, so the
#: Fusion server clock (New York + 7 h) is UTC+2 on the Friday and UTC+3 on the Monday.
FRI_PRE_SWITCH_UTC = datetime(2027, 3, 12, 20, 0, tzinfo=UTC)
MON_POST_SWITCH = datetime(2027, 3, 15, 10, 0, tzinfo=UTC)


def test_a_fusion_deal_from_before_the_us_switch_keeps_its_pre_switch_offset() -> None:
    """Opened Friday before the US change, converted on Monday with a fresh +3 h tick: the stamp
    is converted at ITS OWN instant (+2 h), never by the offset measured now."""
    epoch = (FRI_PRE_SWITCH_UTC + timedelta(hours=2)).timestamp()       # broker wall 22:00 Fri
    out = gc.fusion_epoch_to_utc(epoch, 3, MON_POST_SWITCH.timestamp())
    assert out["utc"] == FRI_PRE_SWITCH_UTC.isoformat()
    assert out["offset_h"] == 2 and out["basis"] == gc.BASIS_CALENDAR
    assert out["measured_h"] == 3
    assert out["mismatch"] is None          # outside the measured offset's regime: no cross-check
    # The defect the audit named, pinned as what must NOT happen: now's offset would be 1 h off.
    assert gc.broker_epoch_to_utc(epoch, 3)[0] != FRI_PRE_SWITCH_UTC.isoformat()


def test_the_mismatch_flag_fires_when_measured_and_calendar_disagree() -> None:
    now = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)                     # Fusion is UTC+2
    deal_utc = now - timedelta(hours=1)
    epoch = (deal_utc + timedelta(hours=2)).timestamp()
    agree = gc.fusion_epoch_to_utc(epoch, 2, now.timestamp())
    assert agree["utc"] == deal_utc.isoformat() and agree["mismatch"] is False
    bad = gc.fusion_epoch_to_utc(epoch, 3, now.timestamp())
    assert bad["mismatch"] is True
    assert bad["utc"] == deal_utc.isoformat() and bad["offset_h"] == 2   # calendar still stamps
    assert gc.fusion_epoch_to_utc(epoch, None, now.timestamp())["mismatch"] is None
    assert gc.fusion_epoch_to_utc(0, 2, now.timestamp())["basis"] == gc.BASIS_UNMEASURED


def test_the_regime_bound_is_24h_and_no_transition() -> None:
    now = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
    zones = gc.FTMO_REGIME_ZONES
    assert gc.same_offset_regime(now - timedelta(hours=23), now, zones)
    assert not gc.same_offset_regime(now - timedelta(hours=25), now, zones)
    assert not gc.same_offset_regime(now + timedelta(hours=1), now, zones)
    # Within 24 h but across New York's 2026-11-01 06:00 UTC change: not the same regime.
    nov1 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    assert not gc.same_offset_regime(nov1 - timedelta(hours=8), nov1, zones)
    # Within 24 h but across the EU's 2026-10-25 01:00 UTC change: FTMO's regime ends there too.
    oct25 = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
    assert not gc.same_offset_regime(oct25 - timedelta(hours=12), oct25, zones)
    assert gc.same_offset_regime(oct25 - timedelta(hours=12), oct25, gc.FUSION_REGIME_ZONES)


def test_an_ftmo_deal_older_than_the_bound_stays_unmeasured() -> None:
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    for p in (str(desk), str(desk.parent.parent)):
        if p not in sys.path:
            sys.path.insert(0, p)
    from prop import ftmo_follower as F

    base = {"symbol": F.SYMBOL, "position_id": 9, "commission": 0.0, "fee": 0.0, "swap": 0.0,
            "volume": 0.01, "order": 5, "profit": 1.0, "reason": 4}
    order = SimpleNamespace(ticket=5, sl=3990.0, tp=4020.0, price_open=4000.0)
    # Read 2026-10-31 09:09 UTC, two days after the close: past the 24 h bound.
    later = "2026-10-31T09:09:15+00:00"
    entry = SimpleNamespace(**base, magic=F.MAGIC, entry=0, type=0, price=4000.0,
                            time=EPOCH - 3600)
    exit_ = SimpleNamespace(**base, magic=F.MAGIC, entry=1, type=1, price=4001.0, time=EPOCH)
    rows = F.compose_fills([entry, exit_], [order], set(), account_key="k", contract=100.0,
                           recorded_at=later, offset_h=3)
    assert rows[0]["timestamp_basis"] == gc.BASIS_UNMEASURED
    assert rows[0]["exit_time"] == "2026-10-29T12:09:01+00:00"           # raw, not converted
    assert rows[0]["broker_utc_offset_h"] is None
    assert rows[0]["broker_utc_offset_measured_h"] == 3
    # A recent exit with an entry older than the bound: the whole row stays unconverted.
    old_entry = SimpleNamespace(**{**vars(entry), "time": EPOCH - 30 * 3600})
    mixed = F.compose_fills([old_entry, exit_], [order], set(), account_key="k", contract=100.0,
                            recorded_at="2026-10-29T09:09:15+00:00", offset_h=3)
    assert mixed[0]["timestamp_basis"] == gc.BASIS_UNMEASURED
    assert mixed[0]["entry_time"] == datetime.fromtimestamp(EPOCH - 30 * 3600, tz=UTC).isoformat()
