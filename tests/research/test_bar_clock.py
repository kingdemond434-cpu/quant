"""The event lane was entering two to three hours BEFORE the news, and nothing could see it.

THE BUG, and it was live. `mt5desk/family_event_reaction` localised an event's `knowable_at` to
UTC and called `searchsorted` on the bar index to find the first bar opening at or after it. The
bar index is BROKER time carrying a UTC tzinfo -- +2 in winter, +3 in summer, measured by
`research/futures_lead_lag` against a feed stamped in epoch seconds (0.978 correlation at the
right offset against 0.10 at zero). So an event at 14:30 genuinely-UTC landed on the bar LABELLED
14:00, which in summer is really the 11:00-12:00 UTC bar.

That is not lateness, which would merely lose money honestly. It is a LOOK-AHEAD: the entry sits
on a bar that opened while the filing was still private, and the error is largest exactly where
the lane is supposed to work, because the drift into a scheduled release happens in those hours.
A backtest of it comes out better than the strategy.

WHAT THESE TESTS PIN:

    NOTHING IS EVER GUESSED. With no measured clock the conversion returns None and the caller
    drops the row. A constant +2 would be right for half the year -- which is exactly the defect
    `broker_clock_measured.json` already has, recording offset_by_trough 2 beside offset_by_peak 3
    on all ten symbols and storing one scalar.

    RAW IS NEVER A FALLBACK. An unconverted stamp is not the conservative choice; it IS the bug.
    A test asserts the unconvertible event is dropped rather than passed through.

    SHOULDER MONTHS ARE REFUSED. March, April, October and November lie between the measured
    windows and depend on a changeover date nothing here measures. A gap in a fraction of the
    year is visible; an hour of error in the same fraction is not.

    THE SHRINKAGE IS COUNTED. A study that quietly loses a third of its events is a different
    study, so every dropped row is accounted for by reason.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from libs.research import bar_clock as bc  # noqa: E402


def _clock(root: Path, *, summer: int | None = 3, winter: int | None = 2,
           agrees: bool = True) -> Path:
    p = root / Path(*bc.CLOCK_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"per_season": {
        "summer": {"offset_h": summer, "agrees_across_pairs": agrees},
        "winter": {"offset_h": winter, "agrees_across_pairs": agrees},
    }}), encoding="utf-8")
    return root


def test_no_measured_clock_converts_nothing(tmp_path):
    """Zero is the one value guaranteed wrong: these bars are on no UTC-equivalent clock in
    either season."""
    got, status, why = bc.to_bar_time(datetime(2026, 7, 1, 14, 30, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED
    assert "futures_lead_lag" in why


def test_summer_and_winter_use_their_own_offset(tmp_path):
    _clock(tmp_path)
    s, st, _ = bc.to_bar_time(datetime(2026, 7, 1, 14, 30, tzinfo=UTC), tmp_path)
    w, wt, _ = bc.to_bar_time(datetime(2026, 1, 15, 14, 30, tzinfo=UTC), tmp_path)
    assert st == wt == bc.OK
    assert s.hour == 17 and w.hour == 16


def test_a_shoulder_month_is_refused_rather_than_given_a_neighbours_offset(tmp_path):
    _clock(tmp_path)
    for when in (datetime(2026, 3, 20, 12, 0, tzinfo=UTC),
                 datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
                 datetime(2026, 10, 20, 12, 0, tzinfo=UTC),
                 datetime(2026, 11, 5, 12, 0, tzinfo=UTC)):
        got, status, why = bc.to_bar_time(when, tmp_path)
        assert got is None and status == bc.SHOULDER, when
        assert "changeover" in why


def test_the_window_edges_are_respected_not_the_month(tmp_path):
    """The windows end mid-month deliberately, to stay clear of the changeover."""
    _clock(tmp_path)
    inside, st, _ = bc.to_bar_time(datetime(2026, 9, 15, 12, 0, tzinfo=UTC), tmp_path)
    outside, so, _ = bc.to_bar_time(datetime(2026, 9, 16, 12, 0, tzinfo=UTC), tmp_path)
    assert st == bc.OK and inside is not None
    assert so == bc.SHOULDER and outside is None


def test_a_season_whose_pairs_disagree_is_not_used(tmp_path):
    """Two instruments on the same broker must give the same clock; if they do not, nothing is
    measured and a number would be a coin flip."""
    _clock(tmp_path, agrees=False)
    got, status, _ = bc.to_bar_time(datetime(2026, 7, 1, 12, 0, tzinfo=UTC), tmp_path)
    assert got is None and status == bc.UNMEASURED


def test_winter_wraps_the_new_year(tmp_path):
    _clock(tmp_path)
    for when in (datetime(2025, 12, 20, 9, 0, tzinfo=UTC),
                 datetime(2026, 1, 20, 9, 0, tzinfo=UTC),
                 datetime(2026, 2, 10, 9, 0, tzinfo=UTC)):
        got, status, _ = bc.to_bar_time(when, tmp_path)
        assert status == bc.OK and got.hour == 11, when


def test_a_batch_accounts_for_every_row(tmp_path):
    """A study that quietly loses a third of its events is a different study."""
    _clock(tmp_path)
    stamps = ([datetime(2026, 7, 1, 12, 0, tzinfo=UTC)] * 3
              + [datetime(2026, 4, 1, 12, 0, tzinfo=UTC)] * 2)
    out = bc.convert_many(stamps, tmp_path)
    assert out["n_in"] == 5 and out["n_kept"] == 3
    assert out["dropped"][bc.SHOULDER] == 2
    assert out["coverage"] == 0.6
    assert "LOOK-AHEAD" in out["rule"]


def test_the_module_never_rewrites_a_bar_index():
    """Bars are what the broker sent. Rewriting an index would silently invalidate every artifact
    keyed on it, and this desk has one clock defect already."""
    src = (_ROOT / "libs" / "research" / "bar_clock.py").read_text(encoding="utf-8")
    for forbidden in ("to_parquet", "write_text", "tz_convert", "reindex", "subprocess"):
        assert forbidden not in src, f"bar_clock reached for {forbidden}"


# ------------------------------------------------------- the lane this was written to fix ------
def _bars(n: int = 400, start: str = "2026-07-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="1h", tz="UTC", name="time")
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                         "close": close, "tick_volume": 100}, index=idx)


def test_the_event_lane_enters_after_the_news_in_the_bars_own_clock(tmp_path, monkeypatch):
    """The whole bug in one assertion: a 12:00 UTC event must not enter on the 12:00 BAR, which
    in summer opened at 09:00 UTC -- three hours before the filing existed."""
    from mt5desk import family_event_reaction as fe

    _clock(tmp_path)
    monkeypatch.setattr(fe, "to_bar_time",
                        lambda when, root=None: bc.to_bar_time(when, tmp_path))
    df = _bars()
    at = "2026-07-05T12:00:00+00:00"
    sig = fe.family_event_reaction(df, events=[{"symbol": "X", "at": at}], symbol="X",
                                   mode="drift", side=1, clock="utc")
    assert sig, "the event produced no signal at all"
    entry = sig[0].time
    assert entry >= pd.Timestamp("2026-07-05T15:00:00+00:00"), (
        f"entered at {entry}: the bar index is broker time (+3 in summer), so a 12:00 UTC event "
        "is only knowable from the 15:00-labelled bar onward")


def test_an_unconvertible_event_is_dropped_not_used_raw(tmp_path, monkeypatch):
    """Raw is not a conservative fallback -- it is the bug."""
    from mt5desk import family_event_reaction as fe

    monkeypatch.setattr(fe, "to_bar_time",
                        lambda when, root=None: bc.to_bar_time(when, tmp_path))  # no clock file
    df = _bars()
    sig = fe.family_event_reaction(df, events=[{"symbol": "X", "at": "2026-07-05T12:00:00+00:00"}],
                                   symbol="X", mode="drift", side=1, clock="utc")
    assert sig == [], "an event was placed with no measured clock"


@pytest.mark.parametrize("month,expect_h", [(7, 3), (1, 2)])
def test_the_offset_applied_is_the_seasons_own(tmp_path, monkeypatch, month, expect_h):
    from mt5desk import family_event_reaction as fe

    _clock(tmp_path)
    monkeypatch.setattr(fe, "to_bar_time",
                        lambda when, root=None: bc.to_bar_time(when, tmp_path))
    start = f"2026-{month:02d}-01"
    df = _bars(start=start)
    at = f"2026-{month:02d}-05T12:00:00+00:00"
    sig = fe.family_event_reaction(df, events=[{"symbol": "X", "at": at}], symbol="X",
                                   mode="drift", side=1, clock="utc")
    assert sig
    assert sig[0].time >= pd.Timestamp(at) + pd.Timedelta(hours=expect_h)


def test_the_default_frame_converts_nothing(tmp_path, monkeypatch):
    """A default of "utc" would have shifted every existing caller's events by hours the moment
    this landed -- including callers whose stamps were already in the bars' frame -- turning a
    fix for a look-ahead into a new one."""
    from mt5desk import family_event_reaction as fe

    _clock(tmp_path)
    monkeypatch.setattr(fe, "to_bar_time",
                        lambda when, root=None: bc.to_bar_time(when, tmp_path))
    df = _bars()
    at = "2026-07-05T12:00:00+00:00"
    default = fe.family_event_reaction(df, events=[{"symbol": "X", "at": at}], symbol="X",
                                       mode="drift", side=1)
    converted = fe.family_event_reaction(df, events=[{"symbol": "X", "at": at}], symbol="X",
                                         mode="drift", side=1, clock="utc")
    assert default and converted
    assert default[0].time == pd.Timestamp(at), "the default frame moved a stamp"
    assert converted[0].time == default[0].time + pd.Timedelta(hours=3)


def test_an_unknown_frame_is_refused_rather_than_assumed():
    from mt5desk import family_event_reaction as fe

    assert fe.family_event_reaction(_bars(), events=[{"symbol": "X", "at": "2026-07-05T12:00:00Z"}],
                                    symbol="X", mode="drift", side=1, clock="broker") == []
    assert set(fe.CLOCKS) == {"bars", "utc"}


def test_the_real_event_source_declares_utc():
    """The calendar is genuinely UTC; the bars are not. `family_inputs` must say so, or the lane
    silently returns to entering before the news."""
    src = (_DESK / "mt5desk" / "family_inputs.py").read_text(encoding="utf-8")
    block = src.split('if family == "event_reaction":', 1)[1].split("return extra", 1)[0]
    assert 'extra["clock"] = "utc"' in block
