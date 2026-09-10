"""A weekly series read a day early is a look-ahead on every observation it has.

WHAT WAS WRONG, and the whole chain is verifiable from this repository with no box:

    scripts/refresh_cot_zcache.py:91   indexes the cache on `report_date_as_yyyy_mm_dd` -- the
                                       TUESDAY the CFTC report is AS-OF -- and forward-fills daily
    data/cot/*.parquet                 carry `report_date` and NO release column at all, so no
                                       stage of the pipeline ever knew when the number went public
    orthogonal_sweep._cot_frame        resamples that to `W-FRI`, labelling each observation
                                       Friday 00:00
    family_cot_positioning             `d.index.searchsorted(ts)` enters at the first bar from
                                       that label onward

The CFTC publishes each Tuesday report at 15:30 ET on the FOLLOWING FRIDAY -- 20:30 UTC, the same
Friday the label names. So the family was entering roughly twenty hours before the data existed,
and about a day once the bar clock is counted, ON EVERY ONE of the 26 years of observations.

WHY THE LAG IS THREE DAYS AND NOT 20.5 HOURS. Two clocks would have to be right for a precise
stamp: the release instant in UTC moves with US daylight saving (20:30 or 19:30), and the bar
index is BROKER time under a UTC tzinfo (+2 winter, +3 summer). Monday is unambiguously after the
release under every combination. It costs nothing, because FX is closed from Friday 21:00 UTC
until Sunday's open -- a signal released Friday evening could not have been traded before then,
so the lag gives up no tradeable time at all.

DIRECTION MATTERS HERE. This makes the family strictly LESS informed, which can only remove
signals that were reading the future. It is not a risk reduction and it caps nothing: it stops an
entry from being placed before its own evidence exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from desks.mt5.research import orthogonal_sweep as osw  # noqa: E402


def test_the_lag_clears_the_release_under_every_clock():
    """20.5h would be exact only if both the DST rule and the broker offset were pinned."""
    assert osw.COT_RELEASE_LAG_DAYS == 3
    # A Tuesday report is released 15:30 ET the following Friday. The W-FRI label is that Friday
    # 00:00; the release is 19:30 or 20:30 UTC the same day; the bar index runs 2-3h ahead.
    label = pd.Timestamp("2026-08-14T00:00:00Z")                 # the Friday label
    latest_release = pd.Timestamp("2026-08-14T20:30:00Z")        # 15:30 ET, standard time
    worst_bar_clock = pd.Timedelta(hours=3)                      # summer broker offset
    lagged = label + pd.Timedelta(days=osw.COT_RELEASE_LAG_DAYS)
    assert lagged > latest_release + worst_bar_clock


def test_the_lag_gives_up_no_tradeable_time():
    """FX is closed Friday 21:00 UTC to Sunday ~21:00 UTC, so a Friday-evening release is not
    tradeable before the weekly open anyway."""
    label = pd.Timestamp("2026-08-14T00:00:00Z")
    lagged = label + pd.Timedelta(days=osw.COT_RELEASE_LAG_DAYS)
    assert lagged.dayofweek == 0, "the lagged label should land on Monday"
    weekly_open = pd.Timestamp("2026-08-16T21:00:00Z")           # Sunday's open
    assert lagged >= weekly_open - pd.Timedelta(hours=24)


def test_the_series_is_shifted_past_its_own_report_date(tmp_path, monkeypatch):
    """The cache is indexed on the Tuesday. Every label must move past the Friday release."""
    idx = pd.date_range("2020-01-01", periods=900, freq="D", tz="UTC")
    frame = pd.DataFrame({"AUDUSD": range(len(idx))}, index=idx)
    cache = tmp_path / "data" / "cot_zcache.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(cache)

    monkeypatch.setattr(osw, "BASE", tmp_path / "desks" / "mt5")
    osw._cot_frame.cache_clear()
    got = osw._cot_frame("AUDUSD")
    assert got is not None and len(got) >= 52

    # Every label is a MONDAY: the W-FRI right edge plus the release lag.
    assert set(got.index.dayofweek) == {0}, "a label did not clear the Friday release"
    # And each value is the one that was public by then -- never a later week's.
    unlagged = frame["AUDUSD"].astype(float).resample("W-FRI").last().dropna()
    assert list(got["net"])[:20] == list(unlagged)[:20], "the lag changed the VALUES, not just the stamps"
    osw._cot_frame.cache_clear()


def test_an_absent_cache_is_still_absent(tmp_path, monkeypatch):
    """The lag must not turn a missing input into a fabricated one."""
    monkeypatch.setattr(osw, "BASE", tmp_path / "desks" / "mt5")
    osw._cot_frame.cache_clear()
    assert osw._cot_frame("NOPE") is None
    osw._cot_frame.cache_clear()


def test_the_raw_source_carries_no_release_date():
    """The reason nothing lagged it: the CFTC extract this desk stores has the as-of date and
    nothing else, so every consumer had to know the publication rule and none did."""
    parquets = sorted((_DESK / "data" / "cot").glob("*.parquet"))
    if not parquets:
        pytest.skip("no COT parquets in this tree -- UNMEASURED, not a pass")
    cols = set(pd.read_parquet(parquets[0]).columns)
    assert "report_date" in cols
    assert not {c for c in cols if any(k in c.lower()
                                       for k in ("release", "publish", "available"))}


def test_the_refresh_still_indexes_on_the_report_date():
    """Pinned deliberately. The cache SHOULD stay keyed on the as-of date -- that is what the
    number is -- and the lag belongs at the reader, where the trading decision is taken. If the
    refresh ever starts writing release dates instead, this lag would double-count and the test
    is what says so."""
    src = (_ROOT / "scripts" / "refresh_cot_zcache.py").read_text(encoding="utf-8")
    assert "report_date_as_yyyy_mm_dd" in src
    assert "COT_RELEASE_LAG_DAYS" not in src, "the lag was applied twice"
