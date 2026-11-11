"""The tape families' reader sees the WHOLE recorded tape, and says the same thing the old one did.

Until 2026-11-11 `orthogonal_sweep._tape_series` read the newest 30 day files only, so the
`liquidity_regime` and `orderflow_imbalance` conditioning series was NaN outside the last thirty
days and no cell could reach the 60-day CPCV history (JUDGE_COVERAGE 2026-11-10: 55,526 cells
mined, 0 judged). These pin three things: on the window the old reader saw, the new one returns
the same numbers; outside it, the new one has data where the old one had NaN; and a day whose
ticks were archived off the box keeps its minutes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import orthogonal_sweep as ow  # noqa: E402

SYM = "EURUSD"


def _old_tape_series(tape: Path, index, rule: str):
    """The pre-2026-11-11 reader, verbatim but for the resample rule being passed in."""
    frames = [pd.read_parquet(f, columns=["ts", "bid", "ask"])
              for f in sorted((tape / SYM).glob("*.parquet"))[-30:]]
    t = pd.concat(frames, ignore_index=True)
    t["ts"] = pd.to_datetime(t["ts"], utc=True)
    t = t.dropna(subset=["bid", "ask"]).sort_values("ts").set_index("ts")
    spread = (t["ask"] - t["bid"]).resample(rule).mean()
    mid = (t["ask"] + t["bid"]) / 2.0
    step = mid.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    flow = step.resample(rule).sum()
    return spread.reindex(index).ffill(), flow.reindex(index).ffill()


def _write_days(tape: Path, days: list[str], seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    for day in days:
        start = pd.Timestamp(f"{day} 00:00", tz="UTC")
        # distinct, strictly increasing stamps (no ties: the old reader's sort was not stable)
        secs = np.sort(rng.choice(86_400 * 1000, size=900, replace=False))
        ts = start + pd.to_timedelta(secs, unit="ms")
        mid = 1.1 + np.cumsum(rng.normal(0, 1e-5, size=len(ts)))
        half = rng.uniform(2e-6, 9e-6, size=len(ts))
        bid, ask = mid - half, mid + half
        bid[5] = np.nan                                   # a one-sided quote is dropped
        p = tape / SYM / f"{day}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"ts": ts, "bid": bid, "ask": ask}).to_parquet(p)


@pytest.fixture()
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tape = tmp_path / "tape" / "ticks"
    monkeypatch.setattr(ow, "TAPE", tape)
    monkeypatch.setattr(ow, "TAPE_AGG", tmp_path / "tape" / "agg_m1")
    monkeypatch.setattr(ow, "_resample_rule", lambda tf: {"M5": "5min", "H1": "60min"}[tf])
    ow._tape_minutes.cache_clear()
    yield tape
    ow._tape_minutes.cache_clear()


@pytest.mark.parametrize("tf", ["M5", "H1"])
def test_inside_the_old_window_the_numbers_are_the_old_numbers(rig: Path, tf: str) -> None:
    days = [str(d.date()) for d in pd.date_range("2026-10-01", periods=6)]
    _write_days(rig, days)
    rule = {"M5": "5min", "H1": "60min"}[tf]
    index = pd.date_range("2026-10-01", "2026-10-06 23:00", freq=rule, tz="UTC")
    old_s, old_f = _old_tape_series(rig, index, rule)
    new_s, new_f = ow._tape_series(SYM, index, tf)
    pd.testing.assert_series_equal(new_s, old_s, check_names=False, check_freq=False,
                                   rtol=1e-12, atol=0)
    pd.testing.assert_series_equal(new_f.astype("float64"), old_f.astype("float64"),
                                   check_names=False, check_freq=False)


def test_the_cached_read_matches_the_first_read(rig: Path) -> None:
    days = [str(d.date()) for d in pd.date_range("2026-10-01", periods=4)]
    _write_days(rig, days)
    index = pd.date_range("2026-10-01", "2026-10-04 23:00", freq="60min", tz="UTC")
    first = ow._tape_series(SYM, index, "H1")
    cached = sorted((ow.TAPE_AGG / SYM).glob("*.parquet"))
    assert [c.name.split(".")[0] for c in cached] == days[:-1], "the open day is never cached"
    ow._tape_minutes.cache_clear()
    again = ow._tape_series(SYM, index, "H1")
    for a, b in zip(first, again, strict=True):
        pd.testing.assert_series_equal(a, b)


def test_history_beyond_thirty_days_is_now_read(rig: Path) -> None:
    days = [str(d.date()) for d in pd.date_range("2026-08-01", periods=45)]
    _write_days(rig, days)
    index = pd.date_range("2026-08-01", "2026-09-14 23:00", freq="60min", tz="UTC")
    old_s, _ = _old_tape_series(rig, index, "60min")
    new_s, new_f = ow._tape_series(SYM, index, "H1")
    early = index < pd.Timestamp("2026-08-16", tz="UTC")
    assert old_s[early].isna().all(), "the old reader saw only the newest 30 files"
    assert new_s[early].notna().sum() > 300 and new_f[early].notna().sum() > 300


def test_a_day_archived_off_the_box_keeps_its_minutes(rig: Path) -> None:
    days = [str(d.date()) for d in pd.date_range("2026-10-01", periods=5)]
    _write_days(rig, days)
    index = pd.date_range("2026-10-01", "2026-10-05 23:00", freq="60min", tz="UTC")
    before = ow._tape_series(SYM, index, "H1")
    (rig / SYM / f"{days[0]}.parquet").unlink()            # archive_tape moved it away
    ow._tape_minutes.cache_clear()
    after = ow._tape_series(SYM, index, "H1")
    for a, b in zip(before, after, strict=True):
        pd.testing.assert_series_equal(a, b)


def test_a_rewritten_day_is_aggregated_again(rig: Path) -> None:
    days = ["2026-10-01", "2026-10-02", "2026-10-03"]
    _write_days(rig, days)
    index = pd.date_range("2026-10-01", "2026-10-03 23:00", freq="60min", tz="UTC")
    ow._tape_series(SYM, index, "H1")
    _write_days(rig, days[:1], seed=99)                    # a late tick rewrites day one
    ow._tape_minutes.cache_clear()
    new_s, _ = ow._tape_series(SYM, index, "H1")
    old_s, _ = _old_tape_series(rig, index, "60min")
    pd.testing.assert_series_equal(new_s, old_s, check_names=False, check_freq=False,
                                   rtol=1e-12, atol=0)
    assert len(list((ow.TAPE_AGG / SYM).glob(f"{days[0]}.*.parquet"))) == 1


def test_no_tape_is_none(rig: Path) -> None:
    idx = pd.date_range("2026-10-01", periods=3, freq="60min", tz="UTC")
    assert ow._tape_series(SYM, idx, "H1") == (None, None)


def test_both_naming_eras_are_read_in_day_order(rig: Path) -> None:
    """The box carries `YYYY-MM-DD.parquet` (older) and `YYYYMMDD.parquet` (newer). A lexical
    sort puts every dashed name first, so the order and the open day must come from the DAY."""
    days = [str(d.date()) for d in pd.date_range("2026-10-01", periods=4)]
    _write_days(rig, days)
    index = pd.date_range("2026-10-01", "2026-10-04 23:00", freq="60min", tz="UTC")
    before = ow._tape_series(SYM, index, "H1")
    for day in days[2:]:                                   # the newer era: compact names
        src = rig / SYM / f"{day}.parquet"
        src.rename(src.with_name(day.replace("-", "") + ".parquet"))
    for f in (ow.TAPE_AGG / SYM).glob("*.parquet"):
        f.unlink()
    ow._tape_minutes.cache_clear()
    after = ow._tape_series(SYM, index, "H1")
    for a, b in zip(before, after, strict=True):
        pd.testing.assert_series_equal(a, b)
    cached = {p.name.split(".")[0] for p in (ow.TAPE_AGG / SYM).glob("*.parquet")}
    assert "20261004" not in cached, "the newest DAY is the open one, whatever its name form"
    assert ow.TAPE_READ_STATS[SYM] == {"days": 4, "archived_days": 0, "undateable_files": 0,
                                       "split_minutes": 0}


def test_a_renamed_day_is_not_read_twice(rig: Path) -> None:
    """A day cached under its dashed name and now resident under its compact name is one day."""
    days = ["2026-10-01", "2026-10-02", "2026-10-03"]
    _write_days(rig, days)
    index = pd.date_range("2026-10-01", "2026-10-03 23:00", freq="60min", tz="UTC")
    before = ow._tape_series(SYM, index, "H1")
    src = rig / SYM / "2026-10-01.parquet"
    src.rename(src.with_name("20261001.parquet"))          # its old aggregate stays cached
    ow._tape_minutes.cache_clear()
    after = ow._tape_series(SYM, index, "H1")
    for a, b in zip(before, after, strict=True):
        pd.testing.assert_series_equal(a, b)
    assert ow.TAPE_READ_STATS[SYM]["archived_days"] == 0


def test_a_minute_split_across_two_files_is_counted(rig: Path) -> None:
    _write_days(rig, ["2026-10-01", "2026-10-02"])
    late = pd.DataFrame({"ts": [pd.Timestamp("2026-10-01 23:59:59.5", tz="UTC")],
                         "bid": [1.1], "ask": [1.10001]})
    p = rig / SYM / "2026-10-02.parquet"
    pd.concat([late, pd.read_parquet(p)], ignore_index=True).to_parquet(p)
    ow._tape_series(SYM, pd.date_range("2026-10-01", periods=48, freq="60min", tz="UTC"), "H1")
    first = pd.read_parquet(rig / SYM / "2026-10-01.parquet")
    last_minute = pd.to_datetime(first["ts"], utc=True).max().floor("min")
    expected = int(last_minute == pd.Timestamp("2026-10-01 23:59", tz="UTC"))
    assert ow.TAPE_READ_STATS[SYM]["split_minutes"] == expected
