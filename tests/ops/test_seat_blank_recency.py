"""A SEAT IS SWAPPED ON WHAT IT IS DOING NOW, NOT ON WHAT IT HAS EVER DONE -- AND ONLY AGAINST A
DENOMINATOR.

`seat_blanks` is a lifetime counter that nothing anywhere resets or decays, so the `seat-chronic-*`
fence keyed on it fired on every run forever once a seat crossed 3 -- whatever the seat was
currently doing. A gate that cannot clear carries zero information, and this one's recommendation
is to SWAP, which costs a live seat off a roster the session banner already reported under-driven.

Measured 2026-08-13: nemotron-3-super-120b-a12b sat at a lifetime 4 while the free-roster canary
reported it ALIVE and answering with 4/4 seats up.

TWO PROPERTIES, AND THE SECOND WAS THE INVERTED ONE (R0570). Recency alone left the fence able to
clear ONLY on a new blank: with no events it read UNMEASURED forever, so it was lit precisely
while the seats were healthy. Attempts are recorded on every call, so health now clears it from
SUCCESS -- the only direction that can honestly do so.

The tests that matter most are still the UNMEASURED ones. Both halves could easily have made the
fence quiet on a box where nothing was recorded, which would clear it on exactly the history that
raised it -- absence resolving to a clean verdict, this desk's most-repeated defect class.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import scripts.max_audit as ma
from scripts.build_audit_coverage import blank_rate, recent_attempts, recent_blanks

_SEAT = "nvidia/nemotron-3-super-120b-a12b:free"
_OTHER = "poolside/laguna-s-2.1:free"


def _events(*ages_days, model=_SEAT):
    now = datetime.now(tz=UTC)
    return [{"model": model, "ts": (now - timedelta(days=d)).isoformat()} for d in ages_days]


def _attempts(n, *, model=_SEAT, days_ago=0):
    day = (datetime.now(tz=UTC).date() - timedelta(days=days_ago)).isoformat()
    return {model: {day: n}}


def _coverage(**kw):
    """Healthy default: the panel has called this seat enough times to grade it."""
    base = {"files": {}, "code_budget_chars": 200000, "seat_blanks": {_SEAT: 4},
            "seat_attempts": _attempts(20)}
    base.update(kw)
    return base


def _seat_defects(m):
    d: list[tuple[str, str]] = []
    ma._check_chronic_seats(d, m)
    return d


class TestRecencyCannotBeFabricatedFromSilence:
    def test_no_attempts_recorded_reads_unmeasured_not_healthy(self):
        """The one that would have quietly disarmed the fence."""
        [(key, msg)] = _seat_defects(_coverage(seat_attempts={}))
        assert key.endswith("-unmeasured")
        assert "UNMEASURED" in msg and "Do not swap on this" in msg

    def test_recent_blanks_returns_none_rather_than_an_empty_dict(self):
        assert recent_blanks({}, window_days=7) is None
        assert recent_blanks({"seat_blank_events": []}, window_days=7) is None

    def test_recent_attempts_returns_none_rather_than_an_empty_dict(self):
        assert recent_attempts({}, window_days=7) is None
        assert recent_attempts({"seat_attempts": {}}, window_days=7) is None
        assert recent_attempts({"seat_attempts": _attempts(3, days_ago=90)}, window_days=7) is None

    def test_an_empty_window_with_a_real_log_is_a_measurement(self):
        """Events exist and none are recent -- that IS evidence the seat recovered."""
        got = recent_blanks({"seat_blank_events": _events(40, 50)}, window_days=7)
        assert got == {}


class TestTheFenceClearsFromSuccessNotOnlyFromANewBlank:
    """R0570: the property that was inverted. A seat answering every call must be able to go
    green without ever failing again."""

    def test_a_seat_that_only_succeeds_clears_the_fence(self):
        assert _seat_defects(_coverage(seat_attempts=_attempts(20))) == []

    def test_too_few_calls_to_grade_is_unmeasured_not_healthy(self):
        m = _coverage(seat_attempts=_attempts(ma.SEAT_MIN_ATTEMPTS - 1))
        [(key, msg)] = _seat_defects(m)
        assert key.endswith("-unmeasured")
        assert f"{ma.SEAT_MIN_ATTEMPTS - 1} recorded call(s)" in msg

    def test_one_blank_in_two_calls_never_prescribes_a_swap(self):
        """A 50% rate off 2 calls is the confident-wrong direction: it would swap a live seat."""
        m = _coverage(seat_attempts=_attempts(2), seat_blank_events=_events(1))
        [(key, _msg)] = _seat_defects(m)
        assert key.endswith("-unmeasured")

    def test_the_rate_is_reported_with_both_halves(self):
        m = _coverage(seat_attempts=_attempts(10), seat_blank_events=_events(1, 2, 3))
        [(_key, msg)] = _seat_defects(m)
        assert "blanked 3x of 10 calls (30%)" in msg


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


class TestTheDenominatorIsPerSeatAndWindowed:
    def test_attempts_outside_the_window_do_not_count(self):
        m = _coverage(seat_attempts={_SEAT: {
            (datetime.now(tz=UTC).date() - timedelta(days=30)).isoformat(): 99}})
        [(key, _msg)] = _seat_defects(m)
        assert key.endswith("-unmeasured")

    def test_another_seats_calls_are_never_borrowed_as_this_seats_denominator(self):
        m = _coverage(seat_attempts=_attempts(50, model=_OTHER))
        [(key, _msg)] = _seat_defects(m)
        assert key.endswith("-unmeasured")

    def test_blank_rate_pairs_blanks_with_attempts(self):
        m = {"seat_attempts": {**_attempts(10), **_attempts(4, model=_OTHER)},
             "seat_blank_events": _events(1, 2)}
        assert blank_rate(m, window_days=7) == {_SEAT: (2, 10), _OTHER: (0, 4)}

    def test_blank_rate_is_none_when_attempts_are_unrecorded(self):
        assert blank_rate({"seat_blank_events": _events(1)}, window_days=7) is None


class TestTheWriterIsActuallyWired:
    """A reader with no writer is the defect this desk names READ-WITHOUT-WRITER. The pure
    functions above would pass identically if `record_attempt` were never called by anything, so
    these drive the real store (redirected to tmp_path -- never the live ledger)."""

    def test_record_attempt_round_trips_into_a_gradeable_denominator(self, tmp_path,
                                                                     monkeypatch):
        from scripts import build_audit_coverage as bac

        monkeypatch.setattr(bac, "ROOT", tmp_path)
        monkeypatch.setattr(bac, "MANIFEST", tmp_path / "coverage.json")
        monkeypatch.setattr(bac, "_eligible", lambda: [])

        for _ in range(ma.SEAT_MIN_ATTEMPTS):
            bac.record_attempt(_SEAT)

        m = bac.load()
        assert recent_attempts(m, window_days=7) == {_SEAT: ma.SEAT_MIN_ATTEMPTS}
        m["seat_blanks"] = {_SEAT: 4}
        assert _seat_defects(m) == []                 # graded healthy off real recorded calls

    def test_the_panel_records_an_attempt_for_every_seat_it_asks(self):
        """The call site, by inspection: one `record_attempt` at the top of `_one`, before the
        request, so a seat that dies mid-call still lands in its own denominator."""
        import ast
        from pathlib import Path

        src = Path(ma.ROOT / "scripts/run_external_panel.py").read_text("utf-8")
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "_one")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "record_attempt"]
        assert len(calls) == 1, "exactly one attempt per seat per run, or the rate is wrong"

    def test_pruning_keeps_the_window_intact(self, tmp_path, monkeypatch):
        """The cap bounds growth; it must never evict a day the 7d window still needs."""
        from scripts import build_audit_coverage as bac

        monkeypatch.setattr(bac, "ROOT", tmp_path)
        monkeypatch.setattr(bac, "MANIFEST", tmp_path / "coverage.json")
        monkeypatch.setattr(bac, "_eligible", lambda: [])
        old = (datetime.now(tz=UTC).date() - timedelta(days=bac._ATTEMPT_DAY_CAP + 5)).isoformat()
        recent = (datetime.now(tz=UTC).date() - timedelta(days=3)).isoformat()
        bac.save({"files": {}, "seat_attempts": {_SEAT: {old: 99, recent: 7}}})

        bac.record_attempt(_SEAT)

        kept = bac.load()["seat_attempts"][_SEAT]
        assert old not in kept                        # bounded
        assert kept[recent] == 7                      # and the window survived


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
        now = datetime.now(tz=UTC)
        m = {"seat_blank_events": [
            *_events(1, 2),
            {"model": _OTHER, "ts": (now - timedelta(days=1)).isoformat()}]}
        assert recent_blanks(m, window_days=7) == {_SEAT: 2, _OTHER: 1}

    def test_a_malformed_attempt_block_is_skipped_not_crashed(self):
        m = {"seat_attempts": {_SEAT: "junk", _OTHER: {
            datetime.now(tz=UTC).date().isoformat(): 3}}}
        assert recent_attempts(m, window_days=7) == {_OTHER: 3}
