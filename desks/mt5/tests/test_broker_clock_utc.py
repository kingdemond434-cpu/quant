"""Time exits are compared with the wall clock, so a broker bar stamp (New York + 7h, labelled
UTC by the frame builders) must become true UTC first -- 3h earlier in New York summer, 2h in
winter, and the right hour on either side of both US daylight-time changes."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402
from mt5desk import scalp_exec as sx  # noqa: E402
from mt5desk.broker_clock import broker_to_utc  # noqa: E402

from libs.regime import session_clock  # noqa: E402

STAMPS = ["2026-01-14 10:00", "2026-07-14 10:00",
          # US spring-forward (2026-03-08) and fall-back (2026-11-01), both sides
          "2026-03-08 08:00", "2026-03-09 10:00", "2026-11-01 07:00", "2026-11-02 10:00",
          # EU changes, which the broker clock does NOT follow
          "2026-03-29 10:00", "2026-10-25 10:00"]


@pytest.mark.parametrize("stamp", STAMPS)
def test_it_matches_the_session_clock(stamp: str) -> None:
    ts = pd.Timestamp(stamp, tz="UTC")
    assert broker_to_utc(ts) == session_clock.server_to_utc([ts])[0]
    assert broker_to_utc(pd.Timestamp(stamp)) == broker_to_utc(ts)        # naive reads the same


def test_offset_is_three_hours_in_ny_summer_and_two_in_winter() -> None:
    assert broker_to_utc(pd.Timestamp("2026-07-14 10:00", tz="UTC")) == pd.Timestamp(
        "2026-07-14 07:00", tz="UTC")
    assert broker_to_utc(pd.Timestamp("2026-01-14 10:00", tz="UTC")) == pd.Timestamp(
        "2026-01-14 08:00", tz="UTC")
    # Between the EU and US autumn changes (2026-10-25 .. 11-01) the broker is still +3.
    assert broker_to_utc(pd.Timestamp("2026-10-28 10:00", tz="UTC")) == pd.Timestamp(
        "2026-10-28 07:00", tz="UTC")


def test_a_family_deadline_spans_its_bars_in_real_hours_across_the_fall_back() -> None:
    """A 12-bar H1 hold whose bars straddle the US fall-back: the deadline is the entry bar's
    true UTC plus 13 real hours, not the broker stamp plus 13 (which is 2-3h late)."""
    bar = pd.Timestamp("2026-10-31 20:00", tz="UTC")          # broker stamp, NY daylight time
    ttl = pd.Timestamp(dc.family_ttl_until(broker_to_utc(bar), 12))
    assert ttl == pd.Timestamp("2026-10-31 17:00", tz="UTC") + pd.Timedelta(hours=13)
    assert pd.Timestamp(dc.family_ttl_until(bar, 12)) - ttl == pd.Timedelta(hours=3)


def test_a_scalp_deadline_converts_the_forming_bar_then_adds() -> None:
    ft = pd.Timestamp("2026-03-08 08:45", tz="UTC")           # broker stamp after spring-forward
    got = pd.Timestamp(sx.ttl_deadline(broker_to_utc(ft), "M15", 6))
    assert got == broker_to_utc(ft) + pd.Timedelta(minutes=15 * 7)
    # 01:45 New York wall time is still EST (UTC-5): the clocks jump at 02:00.
    assert got == pd.Timestamp("2026-03-08 06:45", tz="UTC") + pd.Timedelta(minutes=105)


def test_the_autumn_repeat_hour_reads_as_the_earlier_instant_and_never_raises() -> None:
    """2026-11-01 01:30 New York happened twice (EDT then EST), so the broker stamp 08:30 names
    two instants. It is read as the first: a time exit built on it can only fire early."""
    stamp = pd.Timestamp("2026-11-01 08:30", tz="UTC")
    got = broker_to_utc(stamp)
    assert got == pd.Timestamp("2026-11-01 05:30", tz="UTC")          # 01:30 EDT
    assert got < pd.Timestamp("2026-11-01 06:30", tz="UTC")           # never the later 01:30 EST
    assert got == session_clock.server_to_utc([stamp])[0]


def test_epoch_seconds_and_the_tape_use_the_same_conversion() -> None:
    from mt5desk import tape
    from mt5desk.broker_clock import broker_epoch_to_utc
    for stamp in [*STAMPS, "2026-11-01 08:30"]:
        sec = int(pd.Timestamp(stamp, tz="UTC").timestamp())
        want = broker_to_utc(pd.Timestamp(stamp, tz="UTC"))
        assert broker_epoch_to_utc(sec) == want
        assert tape.broker_epoch_to_utc(sec) == want.isoformat(timespec="seconds")
    assert broker_epoch_to_utc(0) is None and broker_epoch_to_utc("x") is None


def test_the_family_intent_declares_its_time_exit_clock() -> None:
    """A trade autopsy converts a broker-labelled `ttl_until` and must not convert a UTC one
    again; the intent says which (absent = a legacy broker-labelled row)."""
    src = (DESK / "mt5desk" / "gateway.py").read_text(encoding="utf-8")
    end = src.index("[{name}] FAMILY-EXEC ORDER")
    seg = src[end - 2500:end]
    assert 'ttl_clock="utc"' in seg


def test_every_reader_of_ttl_until_honours_its_clock() -> None:
    """Since the intent's `ttl_until` became true UTC, any reader that shifts it by the broker
    offset must first check `ttl_clock`, or it moves every time exit 2-3h early and calls
    normal exits missed. Pins the trade autopsy (#336) the moment it lands beside this."""
    for path in (DESK / "research").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        if '"ttl_until"' in src and "broker" in src and "intent" in src:
            assert "ttl_clock" in src, f"{path.name} reads ttl_until without its ttl_clock"


def test_a_stamp_with_a_real_offset_is_taken_as_written() -> None:
    """18:00+03:00 is already the instant 15:00Z; only a UTC-labelled or naive stamp is a
    broker wall-clock reading to convert."""
    assert broker_to_utc(pd.Timestamp("2026-07-14 18:00", tz="Etc/GMT-3")) == pd.Timestamp(
        "2026-07-14 15:00", tz="UTC")
