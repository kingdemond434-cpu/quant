"""R0523 -- as-of funding interval from settlement stamps, never from a today-snapshot."""
from __future__ import annotations

from datetime import UTC, datetime

from libs.research.funding_interval_history import (
    as_of_intervals,
    build_history,
    discriminating,
)


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp() * 1000)


def test_the_blind_windows_are_exactly_the_ones_measured_on_the_tape():
    """8h stamps are a SUBSET of the 4h grid, so the classes are separable only when the next 4h
    boundary is 4h-exclusive. These three instants are the ones read off the desk's own tape."""
    assert discriminating(_ms("2026-08-05T11:52:46"))       # next 4h = 12:00, 4h-exclusive
    assert not discriminating(_ms("2026-08-13T06:07:10"))   # next stamp 08:00 for BOTH classes
    assert not discriminating(_ms("2026-08-19T13:07:06"))   # next stamp 16:00 for BOTH classes


def test_a_discriminating_snapshot_separates_the_two_cadences():
    t = _ms("2026-08-05T11:52:46")
    snap = {"t": t, "next_funding_ms": {
        "FOURH": _ms("2026-08-05T12:00:00"),
        "EIGHTH": _ms("2026-08-05T16:00:00"),
    }}
    assert as_of_intervals(snap) == {"FOURH": 4.0, "EIGHTH": 8.0}


def test_a_blind_snapshot_yields_nothing_rather_than_a_default():
    """The failure mode this exists to prevent: defaulting in a blind window would label every 4h
    name as 8h exactly where the measurement cannot see."""
    t = _ms("2026-08-13T06:07:10")
    snap = {"t": t, "next_funding_ms": {"A": _ms("2026-08-13T08:00:00")}}
    assert as_of_intervals(snap) == {}


def test_an_unrecognised_stamp_is_UNKNOWN_never_forced_onto_a_grid():
    t = _ms("2026-08-05T11:52:46")
    snap = {"t": t, "next_funding_ms": {"HOURLY": _ms("2026-08-05T12:30:00"), "JUNK": "nope"}}
    got = as_of_intervals(snap)
    assert got == {"HOURLY": None, "JUNK": None}


def test_build_history_counts_blind_snapshots_instead_of_skipping_them():
    snaps = [
        {"t": _ms("2026-08-05T11:52:00"), "next_funding_ms": {"A": _ms("2026-08-05T12:00:00")}},
        {"t": _ms("2026-08-05T13:00:00"), "next_funding_ms": {"A": _ms("2026-08-05T16:00:00")}},
        {"t": _ms("2026-08-05T05:00:00"), "next_funding_ms": {"A": _ms("2026-08-05T08:00:00")}},
        "not-a-mapping",
    ]
    h = build_history(snaps)
    assert h["snapshots_attempted"] == 4
    assert h["snapshots_blind"] == 2          # the 13:00 and 05:00 instants
    assert h["snapshots_unusable"] == 1
    assert h["snapshots_used"] == 1
    assert h["panel"]["2026-08-05"] == {"A": 4.0}


def test_a_mid_day_disagreement_refuses_rather_than_picking_one():
    """A venue can move a symbol mid-day. Choosing a reading would invent a certainty the stamps
    do not support, so the cell is dropped AND counted."""
    snaps = [
        {"t": _ms("2026-08-05T01:00:00"), "next_funding_ms": {"A": _ms("2026-08-05T04:00:00")}},
        {"t": _ms("2026-08-05T09:00:00"), "next_funding_ms": {"A": _ms("2026-08-05T16:00:00")}},
    ]
    h = build_history(snaps)
    assert h["intra_day_conflicts"] == 1
    assert h["panel"]["2026-08-05"] == {}


def test_an_empty_input_is_unmeasured():
    h = build_history([])
    assert h["measured"] is False
    assert h["n_dates"] == 0
