"""Two families the judge could only ever call never_fires, and why one of them stays that way.

event_reaction: no BAR_CLOCK.json meant `to_bar_time` dropped every event, and the calendar reader
saw the last 60 vintage files only (one week; the gzip rollups unparsed). The clock is now also
MEASURED from the desk's own release calendar against the bars' range spike
(`libs/research/bar_clock_release.py`), never guessed; and the reader reads every vintage.

lvc_asia_london: the M5 ATR basis is the pinned source's own (`InpATRTimeframe = PERIOD_M5`), so
its never_fires is a true verdict and is not touched here.
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[3]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import bar_clock as bc  # noqa: E402
from libs.research import bar_clock_release as rel  # noqa: E402

#: Eight USD releases inside the summer window, stamped as the calendar stamps them.
_RELEASES = [pd.Timestamp(f"2026-07-{d:02d}T08:30:00-04:00") for d in (2, 7, 9, 14, 16, 21, 23, 28)]


def _calendar(root: Path, stamps: list[str]) -> None:
    base = root / Path(*rel.CALENDAR_REL.split("/"))
    base.mkdir(parents=True, exist_ok=True)
    rows = [{"kind": "calendar_vintage", "title": "USD CPI m/m", "symbols": ["USD"],
             "impact": "High", "event_date": s} for s in stamps]
    (base / "discoveries_20260729_0000.json").write_text(json.dumps(rows), encoding="utf-8")


def _bars(root: Path, symbol: str, offset_h: int, seed: int) -> None:
    """H1 bars on a broker clock `offset_h` ahead of UTC, with each release's spike on its bar."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-06-25", "2026-08-05", freq="1h")
    close = 1.0 + np.cumsum(rng.normal(0, 1e-4, len(idx)))
    width = np.abs(rng.normal(1e-3, 2e-4, len(idx)))
    frame = pd.DataFrame({"open": close, "high": close + width, "low": close - width,
                          "close": close}, index=idx)
    for t in _RELEASES:
        label = (t.tz_convert("UTC").tz_localize(None) + pd.Timedelta(hours=offset_h)).floor("1h")
        frame.loc[label, "high"] = frame.loc[label, "close"] + 0.02
    base = root / Path(*rel.UNIVERSE_REL.split("/"))
    base.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(base / f"{symbol}_H1.parquet")


def _tree(tmp_path: Path, offsets: dict[str, int]) -> Path:
    rel._CACHE.clear()
    _calendar(tmp_path, [t.isoformat() for t in _RELEASES])
    for i, (sym, off) in enumerate(offsets.items()):
        _bars(tmp_path, sym, off, seed=i)
    return tmp_path


def test_the_release_spike_measures_the_offset_the_bars_were_built_on(tmp_path):
    for true in (3, 2):
        root = _tree(tmp_path / str(true), {"EURUSD": true, "GBPUSD": true, "USDJPY": true})
        assert rel.offsets(root) == {"summer": true}
        assert bc.offsets(root) == {"summer": true}
        assert bc.sources(root) == {"summer": "release_spike"}
        got, status, _ = bc.to_bar_time(datetime(2026, 7, 1, 12, 30, tzinfo=UTC), root)
        assert status == bc.OK and got.hour == 12 + true


def test_instruments_that_disagree_measure_nothing(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 2, "USDJPY": 3})
    assert rel.offsets(root) == {}
    assert bc.to_bar_time(datetime(2026, 7, 1, 12, 30, tzinfo=UTC), root)[1] == bc.UNMEASURED


def test_too_few_voting_instruments_measure_nothing(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 3})
    assert rel.offsets(root) == {}


def test_a_release_with_no_offset_of_its_own_is_never_a_reference(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 3, "USDJPY": 3})
    _calendar(root, [t.tz_localize(None).isoformat() for t in _RELEASES])     # naive stamps
    rel._CACHE.clear()
    assert rel.offsets(root) == {}


def test_bars_without_a_spike_give_no_clock(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 3, "USDJPY": 3})
    _calendar(root, ["2026-07-03T08:30:00-04:00", "2026-07-08T08:30:00-04:00",
                     "2026-07-10T08:30:00-04:00", "2026-07-15T08:30:00-04:00",
                     "2026-07-17T08:30:00-04:00", "2026-07-22T08:30:00-04:00"])
    rel._CACHE.clear()
    assert rel.offsets(root) == {}


def test_a_season_with_no_releases_stays_unmeasured_and_shoulders_stay_refused(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 3, "USDJPY": 3})
    assert "winter" not in bc.offsets(root)
    assert bc.to_bar_time(datetime(2026, 1, 15, 12, 0, tzinfo=UTC), root)[1] == bc.UNMEASURED
    assert bc.to_bar_time(datetime(2026, 10, 20, 12, 0, tzinfo=UTC), root)[1] == bc.SHOULDER


def test_the_measured_file_wins_over_the_release_reading(tmp_path):
    root = _tree(tmp_path, {"EURUSD": 3, "GBPUSD": 3, "USDJPY": 3})
    p = root / Path(*bc.CLOCK_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"per_season": {
        "summer": {"offset_h": 2, "agrees_across_pairs": True}}}), encoding="utf-8")
    assert bc.offsets(root) == {"summer": 2}
    assert bc.sources(root) == {"summer": "BAR_CLOCK.json"}


def test_the_calendar_reader_reads_every_vintage_including_gzip_rollups(tmp_path, monkeypatch):
    from research import orthogonal_sweep as inputs

    base = tmp_path / "data" / "intelligence" / "ff_calendar_vintage"
    base.mkdir(parents=True)
    stamps = pd.date_range("2026-06-01T12:30:00Z", periods=80, freq="1D")
    for t in stamps[:70]:                         # 70 snapshot files: more than the old 60
        (base / f"discoveries_{t:%Y%m%d}_0000.json").write_text(
            json.dumps([{"event_date": t.isoformat(), "impact": "High"}]), encoding="utf-8")
    with gzip.open(base / "rollup_20260901.jsonl.gz", "wt", encoding="utf-8") as fh:
        for t in stamps[70:]:
            fh.write(json.dumps({"event_date": t.isoformat()}) + "\n")
    monkeypatch.setattr(inputs, "BASE", tmp_path)
    inputs._event_index.cache_clear()
    try:
        idx = inputs._event_index()
    finally:
        inputs._event_index.cache_clear()
    assert len(idx) == 80
    assert idx.min() == stamps[0] and idx.max() == stamps[-1]


def test_lvc_defaults_are_the_pinned_sources_including_the_m5_atr():
    """The source's ATR is `iATR(_Symbol, PERIOD_M5, 14)` and its window 0.50..2.00. The port
    keeps both; a daily ATR would be a different hypothesis, not this one."""
    import inspect

    from mt5desk.families_orthogonal import family_lvc_asia_london
    sig = inspect.signature(family_lvc_asia_london).parameters
    assert sig["atr_n"].default == 14
    assert (sig["min_range_atr"].default, sig["max_range_atr"].default) == (0.50, 2.00)
    assert "atr_timeframe" not in sig          # the chart's own bars: the source's PERIOD_M5
    assert "InpATRTimeframe = PERIOD_M5" in (family_lvc_asia_london.__doc__ or "")
