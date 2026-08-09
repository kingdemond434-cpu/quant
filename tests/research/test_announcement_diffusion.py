"""Tests for the gap-#6 announcement-diffusion screen.

The census names the failure mode precisely: "the announcement INSTANT, not the DATE.  A
date-stamped announcement tested against a daily bar is a SAME-BAR ARTIFACT."  So these tests
concentrate on that one thing:
  1. alignment is strictly causal -- an announcement at instant t never informs a bar containing
     t, and the predicted return starts strictly after t;
  2. a synthetic announcement effect that genuinely LEADS is detected;
  3. the same effect aligned to its OWN bar is killed as an artifact;
  4. date-only input REFUSES to screen rather than silently using the date.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from libs.research.announcement_diffusion import (
    ABSENT,
    CONSTRUCTIONS,
    DATE_ONLY,
    INTERVALS_MIN,
    MIN_EVENTS_PER_CELL,
    MIN_PRECISION,
    NEW_CELLS,
    PRIOR_PARAMETERISATIONS,
    SAME_BAR_CONTROL,
    SECOND,
    SUBSECOND,
    TOTAL_TRIALS,
    Announcement,
    InstantUnavailable,
    available_symbols,
    build_signal,
    containing_bar_index,
    declared_cells,
    desk_latency_summary,
    instant_audit,
    load_announcements,
    recover_instant,
    resolve_asset,
    run_screen,
    screen_announcements,
    screen_cell,
    zscore_visibility,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_BAR_MS = 5 * 60 * 1000


def _opens(n: int) -> np.ndarray:
    return np.array([_T0.timestamp() * 1000.0 + i * _BAR_MS for i in range(n)])


def _ann(instant: datetime | None, *, precision: str = SUBSECOND, tier: int = 1) -> Announcement:
    return Announcement("okx", "t", instant, precision, ("FOO",), tier, 3.0, "test")


# --------------------------------------------------------------------- 1. instant recovery


def test_subsecond_publisher_stamp_is_recovered():
    row = {"source": "okx", "published_at": "2026-07-30T03:00:09.432000+00:00", "tier": 2}
    got = recover_instant(row)
    assert got.precision == SUBSECOND
    assert got.screenable is True
    assert got.instant == datetime(2026, 7, 30, 3, 0, 9, 432000, tzinfo=UTC)


def test_second_resolution_rss_stamp_is_recovered():
    row = {"source": "coindesk", "published_at": "2026-07-31T11:07:52+00:00"}
    got = recover_instant(row)
    assert got.precision == SECOND
    assert got.screenable is True


def test_midnight_exact_stamp_is_diagnosed_as_a_date_not_an_instant():
    """THE LOAD-BEARING DIAGNOSTIC.  A date-only feed parsed naively yields a well-formed aware
    datetime at exactly midnight.  It must be graded DATE_ONLY and refused -- accepting it is
    precisely the same-bar artifact the census warns about."""
    row = {"source": "defillama_hacks", "published_at": "2020-02-18T00:00:00+00:00"}
    got = recover_instant(row)
    assert got.precision == DATE_ONLY
    assert got.screenable is False
    assert "DATE" in got.why


def test_naive_stamp_is_refused_not_localised():
    """Guessing the publishing zone is how a whole-day shift enters.  Refuse instead."""
    got = recover_instant({"source": "x", "published_at": "2026-07-30T03:00:09"})
    assert got.instant is None
    assert got.precision == ABSENT
    assert "naive" in got.why


def test_absent_or_malformed_stamp_is_refused():
    assert recover_instant({"source": "x"}).precision == ABSENT
    assert recover_instant({"source": "x", "published_at": "not-a-time"}).precision == ABSENT


def test_min_precision_is_minute_and_the_grading_is_ordered():
    assert MIN_PRECISION == "minute"
    assert _ann(_T0.replace(hour=3, minute=7), precision="minute").screenable is True
    assert _ann(_T0, precision=DATE_ONLY).screenable is False


# --------------------------------------------------------------------- 2. causal alignment


def test_signal_is_stamped_on_the_bar_containing_the_instant():
    opens = _opens(20)
    inside_bar_4 = _T0 + timedelta(minutes=4 * 5 + 2)
    assert containing_bar_index(inside_bar_4, opens) == 4


def test_instant_on_a_bar_open_belongs_to_that_bar():
    opens = _opens(20)
    exactly_bar_6 = _T0 + timedelta(minutes=30)
    assert containing_bar_index(exactly_bar_6, opens) == 6


def test_instants_outside_the_panel_are_dropped_not_clamped():
    opens = _opens(20)
    assert containing_bar_index(_T0 - timedelta(days=1), opens) == -1
    assert containing_bar_index(_T0 + timedelta(days=10), opens) == -1     # no successor bar


def test_causal_pulse_never_precedes_the_announcement():
    """An announcement at instant t must place nothing on any bar before the one containing t.

    The harness predicts return[k+1], which begins at close_k -- strictly after t.  So the
    return being predicted can never contain the announcement."""
    opens = _opens(30)
    inside_bar_10 = _T0 + timedelta(minutes=10 * 5 + 1)
    sig = build_signal((_ann(inside_bar_10),), opens, construction="A1_event_pulse")
    assert sig[10] == 1.0
    assert np.count_nonzero(sig[:10]) == 0


def test_the_artifact_control_deliberately_fires_one_bar_early():
    """A4 exists to be wrong in the exact way a date-stamped screen is wrong: its predicted
    return is the bar CONTAINING the announcement."""
    opens = _opens(30)
    inside_bar_10 = _T0 + timedelta(minutes=10 * 5 + 1)
    sig = build_signal((_ann(inside_bar_10),), opens, construction=SAME_BAR_CONTROL)
    assert sig[9] == 1.0
    assert sig[10] == 0.0


def test_decay_pulse_spreads_forward_only():
    opens = _opens(30)
    sig = build_signal(
        (_ann(_T0 + timedelta(minutes=51)),), opens, construction="A3_decay_pulse"
    )
    assert np.count_nonzero(sig[:10]) == 0
    assert sig[10] == 1.0
    assert 0.0 < sig[11] < sig[10]


def test_undeclared_construction_is_refused():
    with pytest.raises(ValueError, match="undeclared construction"):
        build_signal((), _opens(5), construction="A9_after_the_fact")


# --------------------------------------------------------------------- 3. lead vs same-bar


#: Slow diffusion: the announcement's effect bleeds across many bars.  This IS the mechanism's
#: claim ("diffuses at finite speed"), and it is also the only shape distinguishable from a
#: lookahead using the arrays alone -- an effect concentrated entirely on bar k+1 makes a true
#: lead and a one-bar leak produce identical statistics, and the harness correctly refuses both.
_DIFFUSION = (1.0, 0.95, 0.88, 0.80, 0.70, 0.58, 0.45, 0.33)

#: Panel size chosen so the harness is POWERED (min_detectable_ic = 1.96/sqrt(n) <= 0.03 needs
#: n > ~4270).  A smaller panel reads SCREEN-UNDERPOWERED regardless of the effect, which is the
#: harness working correctly and would make these tests assert nothing.
_N_BARS = 6000

#: Spacing chosen so announcements are DENSER than the harness's 20-bar z-window; see
#: `zscore_visibility`.  At wider spacing the screen refuses to read at all, which is pinned
#: separately by `test_sparse_events_are_refused_because_the_zscore_cannot_see_them`.
_SPACING = 11


def _price_panel(n: int, event_bars: list[int], *, jump: float, seed: int,
                 on_event_bar: bool) -> tuple[np.ndarray, np.ndarray]:
    """Bars whose announcement effect lands either entirely on the announcement's OWN bar (the
    same-bar artifact) or diffuses over the bars AFTER it (a genuine lead)."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0, 0.004, size=n)
    for k in event_bars:
        if on_event_bar:
            if k < n:
                ret[k] += jump
            continue
        for j, w in enumerate(_DIFFUSION):
            if k + 1 + j < n:
                ret[k + 1 + j] += jump * w
    return _opens(n), 100.0 * np.cumprod(1.0 + ret)


def _events(opens: np.ndarray, event_bars: list[int]) -> tuple[Announcement, ...]:
    """Announcements stamped one minute INTO each event bar, so each falls strictly inside it."""
    return tuple(
        _ann(datetime.fromtimestamp(opens[k] / 1000.0, tz=UTC) + timedelta(minutes=1))
        for k in event_bars
    )


def test_a_genuinely_leading_announcement_effect_is_detected():
    """The move begins on bar k+1 -- entirely after the instant -- and diffuses.  The screen
    must find it, and must not mistake it for an artifact."""
    bars = list(range(60, _N_BARS - 60, _SPACING))
    opens, close = _price_panel(_N_BARS, bars, jump=0.0015, seed=5, on_event_bar=False)
    sig = build_signal(_events(opens, bars), opens, construction="A1_event_pulse")
    out = screen_cell(sig, close, name="lead", interval_min=5, n_events=len(bars))
    assert out["verdict"] == "SCREEN-INTERESTING", out
    assert out["decontam_passed"] is True
    assert out["shift_translates"] is False
    assert out["zscore_visibility"]["readable"] is True


def test_the_same_bar_effect_is_killed_as_an_artifact():
    """THE CENSUS'S NAMED FAILURE MODE, REPRODUCED AND KILLED.

    The whole move lands on bar k -- the bar CONTAINING the announcement -- and the naive
    alignment (A4, one bar early, which is what a date-stamped announcement on a daily bar
    amounts to) 'predicts' it.  That must come back an artifact, never SCREEN-INTERESTING."""
    bars = list(range(60, _N_BARS - 60, _SPACING))
    opens, close = _price_panel(_N_BARS, bars, jump=0.010, seed=5, on_event_bar=True)
    sig = build_signal(_events(opens, bars), opens, construction=SAME_BAR_CONTROL)
    out = screen_cell(
        sig, close, name="same_bar", interval_min=5, n_events=len(bars), charged=False
    )
    assert out["verdict"] in {"TIMING-ARTIFACT", "SUSPECT-LOOKAHEAD"}, out
    assert out["verdict"] != "SCREEN-INTERESTING"
    assert out["shift_translates"] is True     # the leak's fingerprint: lag it and it translates
    assert "ARTIFACT-CONTROL" in out["role"]


def test_the_artifact_is_killed_across_the_whole_effect_size_range():
    """The kill must not depend on the leak being large.  A small same-bar contamination is the
    dangerous one, because it looks like a plausible edge."""
    bars = list(range(60, _N_BARS - 60, _SPACING))
    for jump in (0.004, 0.010, 0.020):
        opens, close = _price_panel(_N_BARS, bars, jump=jump, seed=5, on_event_bar=True)
        sig = build_signal(_events(opens, bars), opens, construction=SAME_BAR_CONTROL)
        out = screen_cell(
            sig, close, name=f"sb_{jump}", interval_min=5, n_events=len(bars), charged=False
        )
        assert out["verdict"] != "SCREEN-INTERESTING", (jump, out)


def test_the_causal_alignment_does_not_promote_a_same_bar_effect():
    """Symmetric to the above.  When the whole move is inside the announcement's own bar there
    is nothing left to predict, so the CAUSAL alignment must not report a find.  If it did, the
    alignment itself would be leaking."""
    bars = list(range(60, _N_BARS - 60, _SPACING))
    opens, close = _price_panel(_N_BARS, bars, jump=0.010, seed=5, on_event_bar=True)
    sig = build_signal(_events(opens, bars), opens, construction="A1_event_pulse")
    out = screen_cell(sig, close, name="causal_on_samebar", interval_min=5, n_events=len(bars))
    assert out["verdict"] != "SCREEN-INTERESTING", out


def test_sparse_events_are_refused_because_the_zscore_cannot_see_them():
    """A DEFECT FOUND WHILE BUILDING THIS SCREEN.  The harness z-scores over a trailing 20-bar
    window and emits 0 when that window has no variance -- so an event sparser than 20 bars is
    annihilated at exactly the bar it fires on, and the screen silently starts measuring
    'an announcement fired recently', sign-inverted.  The cell must refuse, not print a
    verdict about a different question."""
    bars = list(range(60, _N_BARS - 60, 60))       # far wider than the 20-bar z-window
    opens, close = _price_panel(_N_BARS, bars, jump=0.0015, seed=5, on_event_bar=False)
    sig = build_signal(_events(opens, bars), opens, construction="A1_event_pulse")
    vis = zscore_visibility(sig)
    assert vis["event_visibility"] == 0.0        # z is 0 at EVERY event bar
    out = screen_cell(sig, close, name="sparse", interval_min=5, n_events=len(bars))
    assert out["verdict"] == "SCREEN-UNDERPOWERED"
    assert "not refuted" in out["why"]
    assert "ic" not in out                        # no number is published for the wrong question


def test_the_decay_construction_stays_visible_where_the_bare_pulse_does_not():
    """A3 spreads the pulse over DECAY_BARS (> the harness's z-window) precisely so the trailing
    window has variance at the event bar.  That is why the constant is 24 and not 6."""
    bars = list(range(60, _N_BARS - 60, 40))
    opens, _ = _price_panel(_N_BARS, bars, jump=0.001, seed=5, on_event_bar=False)
    evs = _events(opens, bars)
    assert zscore_visibility(build_signal(evs, opens, construction="A1_event_pulse"))[
        "event_visibility"
    ] == 0.0
    assert zscore_visibility(build_signal(evs, opens, construction="A3_decay_pulse"))[
        "readable"
    ] is True


# --------------------------------------------------------------------- 4. refuse, never fake


def test_screening_date_only_announcements_raises_rather_than_using_the_date():
    """THE REQUIREMENT: missing-instant data must refuse to screen, not silently degrade."""
    opens = _opens(1000)
    close = np.full(1000, 100.0)
    dated = tuple(_ann(_T0 + timedelta(days=i), precision=DATE_ONLY) for i in range(30))
    with pytest.raises(InstantUnavailable) as err:
        screen_announcements(dated, opens, close, label="FOO")
    assert "same-bar artifact" in str(err.value)
    assert DATE_ONLY in str(err.value)


def test_a_single_date_only_row_is_enough_to_refuse_the_batch():
    """Silently dropping the unusable rows would report a clean n over a silently-filtered
    sample.  The caller must decide in the open."""
    opens = _opens(1000)
    close = np.full(1000, 100.0)
    mixed = (
        *(_ann(_T0 + timedelta(minutes=5 * i + 1)) for i in range(30)),
        _ann(_T0 + timedelta(days=2), precision=DATE_ONLY),
    )
    with pytest.raises(InstantUnavailable):
        screen_announcements(mixed, opens, close, label="FOO")


def test_missing_announcement_log_is_reported_not_invented(tmp_path):
    rows, missing = load_announcements(tmp_path / "nope.jsonl")
    assert rows == ()
    assert any("absent from this checkout" in m for m in missing)
    report = run_screen(announcements_path=tmp_path / "nope.jsonl", bar_root=tmp_path)
    assert report["status"] == "NOT-READABLE-HERE"
    assert report["power"]["label"] == "INDETERMINATE"
    assert report["graveyard"] == []


def test_a_thin_cell_is_underpowered_not_refuted():
    out = screen_cell(np.zeros(100), np.full(100, 100.0), name="thin", interval_min=5, n_events=2)
    assert out["verdict"] == "SCREEN-UNDERPOWERED"
    assert "not refuted" in out["why"]
    assert out["min_events_required"] == MIN_EVENTS_PER_CELL


def test_quote_currency_is_never_mistaken_for_the_listed_asset():
    """The collector's regex mostly extracts USDT.  Joining a GRVT announcement to the BTC panel
    because both are USDT-quoted would screen pure noise and call it a result."""
    only_quote = Announcement("okx", "t", _T0, SUBSECOND, ("USDT",), 2, 1.0, "w")
    assert resolve_asset(only_quote) is None
    real = Announcement("okx", "t", _T0, SUBSECOND, ("USDT", "TAO"), 2, 1.0, "w")
    assert resolve_asset(real) == "TAOUSDT"
    assert resolve_asset(Announcement("okx", "t", _T0, SUBSECOND, (), 2, 1.0, "w")) is None


# --------------------------------------------------------------------- audit + multiplicity


def test_instant_audit_counts_recoverable_and_refused_per_source():
    rows = (
        _ann(_T0 + timedelta(minutes=1)),
        _ann(_T0, precision=DATE_ONLY),
        Announcement("rss", "t", None, ABSENT, (), 3, None, "no stamp"),
    )
    audit = instant_audit(rows)
    assert audit["n_rows"] == 3
    assert audit["n_instant_recovered"] == 1
    assert audit["n_refused"] == 2
    assert audit["instant_recoverable"] is True
    assert set(audit["by_source"]) == {"okx", "rss"}


def test_desk_latency_is_measured_because_the_slower_participant_pays():
    rows = (
        Announcement("okx", "t", _T0, SUBSECOND, (), 1, 2031.5, "w"),
        Announcement("okx", "t", _T0, SUBSECOND, (), 1, 4000.0, "w"),
        Announcement("dead", "t", _T0, SUBSECOND, (), 1, None, "w"),
    )
    summary = desk_latency_summary(rows)
    assert summary["okx"]["n"] == 2
    assert summary["okx"]["min_minutes"] == 2031.5
    assert summary["dead"]["n"] == 0


def test_this_class_had_no_prior_trials_so_the_charge_is_exactly_the_grid():
    assert PRIOR_PARAMETERISATIONS == 0
    assert NEW_CELLS == len(CONSTRUCTIONS) * len(INTERVALS_MIN) == 9
    assert TOTAL_TRIALS == 9
    # the artifact control runs but is NOT charged: it can never be promoted, so charging it
    # would raise the bar protecting the cells that can.
    assert len(declared_cells()) == NEW_CELLS + len(INTERVALS_MIN)


def test_power_is_reported_beside_every_verdict():
    thin = screen_cell(np.zeros(10), np.full(10, 100.0), name="t", interval_min=5, n_events=0)
    assert thin["power"]["label"] in {"INDETERMINATE", "UNDERPOWERED"}
    assert thin["status"] == "NOT-READABLE-HERE"
    rng = np.random.default_rng(0)
    close = 100.0 * np.cumprod(1.0 + rng.normal(0, 0.002, 4000))
    sig = np.zeros(4000)
    sig[::40] = 1.0
    fat = screen_cell(sig, close, name="f", interval_min=5, n_events=100)
    assert fat["power"]["alpha"] == 0.05
    assert fat["power"]["n_tests"] == TOTAL_TRIALS


# --------------------------------------------------------------------- against real disk data


def test_real_on_disk_announcements_grade_without_crashing():
    """The screen must produce an honest artifact against whatever is actually on disk."""
    rows, missing = load_announcements()
    if missing:
        pytest.skip("announcement log not present in this checkout")
    audit = instant_audit(rows)
    assert audit["n_rows"] > 0
    # The exchange source is the one this gap is about, and its stamps come off an API.
    if "okx" in audit["by_source"]:
        assert audit["by_source"]["okx"].get(SUBSECOND, 0) > 0
    # defillama_hacks is a date-only feed and must be refused wholesale.
    if "defillama_hacks" in audit["by_source"]:
        bucket = audit["by_source"]["defillama_hacks"]
        assert bucket.get(DATE_ONLY, 0) == sum(bucket.values())


def test_available_symbols_reports_the_real_subdaily_panel():
    have = available_symbols()
    assert set(have) == set(INTERVALS_MIN)
    for names in have.values():
        assert all(isinstance(n, str) for n in names)
