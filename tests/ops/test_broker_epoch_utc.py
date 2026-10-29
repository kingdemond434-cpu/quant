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
    assert raw[0]["timestamp_basis"] == "mt5_server_epoch"           # unmeasured: not guessed
    assert raw[0]["exit_time"] == "2026-10-29T12:09:01+00:00"
