"""A SEAT IS SWAPPED ON WHAT IT IS DOING NOW, NOT ON WHAT IT HAS EVER DONE.

`seat_blanks` is a lifetime counter that nothing anywhere resets or decays, so the `seat-chronic-*`
fence keyed on it fired on every run forever once a seat crossed 3 -- whatever the seat was
currently doing. A gate that cannot clear carries zero information, and this one's recommendation
is to SWAP, which costs a live seat off a roster the session banner already reported under-driven.

Measured 2026-08-13: nemotron-3-super-120b-a12b sat at a lifetime 4 while the free-roster canary
reported it ALIVE and answering with 4/4 seats up.

The tests that matter most are the UNMEASURED ones. Adding recency could easily have made the
fence quiet on a box with no event log yet, which would clear it on exactly the history that
raised it -- absence resolving to a clean verdict, this desk's most-repeated defect class.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import scripts.max_audit as ma
from scripts.build_audit_coverage import recent_blanks

_SEAT = "nvidia/nemotron-3-super-120b-a12b:free"


def _events(*ages_days):
    now = datetime.now(tz=UTC)
    return [{"model": _SEAT, "ts": (now - timedelta(days=d)).isoformat()} for d in ages_days]


def _coverage(**kw):
    base = {"files": {}, "code_budget_chars": 200000, "seat_blanks": {_SEAT: 4}}
    base.update(kw)
    return base


def _seat_defects(m):
    d: list[tuple[str, str]] = []
    ma._check_chronic_seats(d, m)
    return d


class TestRecencyCannotBeFabricatedFromSilence:
    def test_no_event_log_reads_unmeasured_not_healthy(self):
        """The one that would have quietly disarmed the fence."""
        [(key, msg)] = _seat_defects(_coverage())
        assert key.endswith("-unmeasured")
        assert "UNMEASURED" in msg and "Do not swap on this" in msg

    def test_recent_blanks_returns_none_rather_than_an_empty_dict(self):
        assert recent_blanks({}, window_days=7) is None
        assert recent_blanks({"seat_blank_events": []}, window_days=7) is None

    def test_an_empty_window_with_a_real_log_is_a_measurement(self):
        """Events exist and none are recent -- that IS evidence the seat recovered."""
        got = recent_blanks({"seat_blank_events": _events(40, 50)}, window_days=7)
        assert got == {}


class TestTheFenceClearsWhenTheSeatRecovers:
    def test_old_blanks_alone_no_longer_fire(self):
        assert _seat_defects(_coverage(seat_blank_events=_events(30, 31, 32))) == []

    def test_blanks_inside_the_window_still_fire(self):
        [(key, msg)] = _seat_defects(_coverage(seat_blank_events=_events(1, 2, 3)))
        assert key == f"seat-chronic-{_SEAT.split('/')[-1]}"
        assert "still happening" in msg and "lifetime 4" in msg

    def test_two_recent_blanks_are_under_the_bar(self):
        """The threshold is unchanged at 3 -- this repair narrows WHEN, never the bar."""
        assert _seat_defects(_coverage(seat_blank_events=_events(1, 2, 40, 41))) == []

    def test_a_seat_below_the_lifetime_bar_never_fires(self):
        m = _coverage(seat_blanks={_SEAT: 2}, seat_blank_events=_events(1, 2))
        assert _seat_defects(m) == []


class TestTheEventLogIsRobustToItsOwnJunk:
    def test_unparseable_stamps_are_skipped_not_crashed(self):
        m = {"seat_blank_events": [{"model": _SEAT, "ts": "not-a-date"}, *_events(1)]}
        assert recent_blanks(m, window_days=7) == {_SEAT: 1}

    def test_non_dict_rows_are_skipped(self):
        m = {"seat_blank_events": ["junk", *_events(1)]}
        assert recent_blanks(m, window_days=7) == {_SEAT: 1}

    def test_a_log_of_only_junk_is_a_measurement_of_zero_recent_blanks(self):
        """Distinct from None: the log exists, it just carries nothing placeable in a window."""
        assert recent_blanks({"seat_blank_events": ["junk"]}, window_days=7) == {}

    def test_seats_are_counted_separately(self):
        other = "poolside/laguna-s-2.1:free"
        now = datetime.now(tz=UTC)
        m = {"seat_blank_events": [
            *_events(1, 2),
            {"model": other, "ts": (now - timedelta(days=1)).isoformat()}]}
        assert recent_blanks(m, window_days=7) == {_SEAT: 2, other: 1}
