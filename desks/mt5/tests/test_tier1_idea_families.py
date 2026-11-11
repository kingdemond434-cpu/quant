"""The Tier-1 idea families (U1-U5, N1), their holiday calendars and their proposer."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_tier1_ideas as t1  # noqa: E402

from research import exchange_holidays as eh  # noqa: E402
from research import tier1_idea_proposer as tp  # noqa: E402


def _bars(days: int = 400, seed: int = 3, weekends: bool = False,
          start: str = "2023-01-02") -> pd.DataFrame:
    """Hourly broker-stamped bars (NY+7, labelled UTC as the desk's parquets are)."""
    idx = pd.date_range(start, periods=days * 24, freq="1h", tz="UTC")
    if not weekends:
        idx = idx[idx.dayofweek < 5]
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    opn = np.concatenate([[100.0], close[:-1]]) * np.exp(rng.normal(0, 0.0005, len(idx)))
    hi = np.maximum(opn, close) * 1.001
    lo = np.minimum(opn, close) * 0.999
    return pd.DataFrame({"open": opn, "high": hi, "low": lo, "close": close}, index=idx)


def test_all_six_are_registered_and_charged_once() -> None:
    from mt5desk import families_orthogonal as fo

    from research import orthogonal_sweep as osw

    for name, fn in t1.TIER1_IDEA_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn
        assert name in fo.FAMILY_INPUTS
        assert name in osw.NOT_SOURCED_HERE, "the proposer owns the search; the sweep must not"
    assert fo.FAMILY_INPUTS["intraday_momentum"][0] == "price only"
    assert fo.FAMILY_INPUTS["overnight_day_tug"][0] == "price only"


def test_intraday_momentum_decides_before_the_last_window_on_the_first_window() -> None:
    d = _bars()
    sigs = t1.family_intraday_momentum(d)
    assert len(sigs) > 200
    _m, ymd = t1.LC.local_frame(d.index, "America/New_York")
    minute, _ = t1.LC.local_frame(d.index, "America/New_York")
    pos = {t: i for i, t in enumerate(d.index)}
    sess = t1.session_bars(d.index, "America/New_York", "09:30", "16:00")
    dates = sorted(sess)
    for s in sigs[:50]:
        i = pos[s.time]
        assert minute[i] == 14 * 60, "decided on the 14:00 bar; the 15:00 bar is the last window"
        day = int(ymd[i])
        prev = dates[dates.index(day) - 1]
        first_end = next(j for j in range(sess[day][0], i) if minute[j] == 9 * 60)
        move = d["close"].iloc[first_end] - d["close"].iloc[sess[prev][1]]
        assert s.side == int(np.sign(move))
        assert s.ttl_bars == 1
    fade = t1.family_intraday_momentum(d, direction="fade")
    assert [s.side for s in fade[:20]] == [-s.side for s in sigs[:20]]
    assert t1.family_intraday_momentum(d, direction="sideways") == []
    assert t1.family_intraday_momentum(d, open_at="9:99") == []


def test_overnight_day_tug_fires_only_when_the_legs_disagree() -> None:
    d = _bars()
    sigs = t1.family_overnight_day_tug(d, min_day_atr=0.0)
    assert sigs
    sess = t1.session_bars(d.index, "America/New_York", "09:30", "16:00")
    by_close = {d.index[c]: (o, c, day) for day, (o, c) in sess.items()}
    dates = sorted(sess)
    for s in sigs[:40]:
        o, c, day = by_close[s.time]
        prev = dates[dates.index(day) - 1]
        night = d["open"].iloc[o] - d["close"].iloc[sess[prev][1]]
        dayleg = d["close"].iloc[c] - d["open"].iloc[o]
        assert night * dayleg < 0
        assert s.side == int(np.sign(night))
        assert s.ttl_bars == round((1440 - 390) / 60)
    day_side = t1.family_overnight_day_tug(d, min_day_atr=0.0, follow="day")
    assert [s.side for s in day_side] == [-s.side for s in sigs]


def test_implied_realised_gap_reads_only_what_was_knowable() -> None:
    d = _bars(days=900)
    days = pd.date_range("2023-01-01", periods=900, freq="1D", tz="UTC")
    iv = pd.Series(20 + 5 * np.sin(np.arange(900) / 30.0), index=days)
    sigs = t1.family_implied_realised_gap(d, implied=iv, z_obs=120, z_lo=0.5)
    assert sigs
    later = iv.copy()
    later.index = later.index + pd.Timedelta(days=200)       # the same values, knowable later
    first_late = t1.family_implied_realised_gap(d, implied=later, z_obs=120, z_lo=0.5)
    assert not first_late or first_late[0].time >= later.index[120]
    assert t1.family_implied_realised_gap(d, implied=iv, implied_series="VIXCLS") == []
    assert t1.family_implied_realised_gap(d, implied=iv, direction="up") == []


def test_weekend_crypto_gap_trades_the_monday_session_not_the_gap() -> None:
    target = _bars(days=900)
    driver = _bars(days=900, seed=9, weekends=True)
    sigs = t1.family_weekend_crypto_gap(target, driver=driver, min_move_sd=0.5)
    assert sigs
    for s in sigs:
        assert s.time.dayofweek == 0
        i = target.index.get_loc(s.time)
        assert target.index[i] - target.index[i - 1] > timedelta(hours=36)
    fade = t1.family_weekend_crypto_gap(target, driver=driver, min_move_sd=0.5, direction="fade")
    assert [s.side for s in fade] == [-s.side for s in sigs]
    disagree = t1.family_weekend_crypto_gap(target, driver=driver, min_move_sd=0.5,
                                            require_gap_disagree=True)
    assert len(disagree) < len(sigs)
    assert t1.family_weekend_crypto_gap(target, driver=driver, driver_symbol="DOGEUSD") == []


def test_equity_gap_breadth_counts_big_gaps_and_trades_the_index_at_the_open() -> None:
    panel = {f"N{i}": _bars(days=200, seed=100 + i) for i in range(30)}
    idx = panel["N0"].index
    sess = t1.session_bars(idx, "America/New_York", "09:30", "16:00")
    _day, (o, _c) = sorted(sess.items())[100]
    for frame in panel.values():                             # a broad gap-up morning
        frame.iloc[o:, :] *= 1.05
    b = t1.gap_breadth(panel, "America/New_York", "09:30", "16:00", gap_sd=2.0, vol_days=20,
                       min_names=20)
    assert b.loc[idx[o]] == pytest.approx(1.0)
    index_bars = _bars(days=200, seed=7)
    sigs = t1.family_equity_gap_breadth(index_bars, breadth=b, breadth_lo=0.5)
    hit = [s for s in sigs if s.time == idx[o]]
    assert hit and hit[0].side == 1
    assert hit[0].ttl_bars == round(390 / 60)
    assert t1.us_share_names(Path("/nonexistent/universe.json")) == ()


def test_holiday_drift_fires_around_the_venue_calendar(tmp_path, monkeypatch) -> None:
    (tmp_path / "holidays_test.json").write_text(json.dumps(
        {"holidays": ["2023-07-04", "2023-11-23", "2023-12-25"]}), "utf-8")
    monkeypatch.setattr(t1, "CALENDARS", tmp_path)
    t1._holidays.cache_clear()
    d = _bars()
    pre = t1.family_holiday_drift(d, calendar="test")
    post = t1.family_holiday_drift(d, calendar="test", leg="post")
    _m, ymd = t1.LC.local_frame(d.index, "America/New_York")
    assert {int(ymd[d.index.get_loc(s.time)]) for s in pre} == {20230630, 20231121, 20231221}
    assert {int(ymd[d.index.get_loc(s.time)]) for s in post} == {20230705, 20231124, 20231226}
    assert all(s.side == 1 for s in pre)
    short = t1.family_holiday_drift(d, calendar="test", direction="short")
    assert all(s.side == -1 for s in short)
    assert t1.family_holiday_drift(d, calendar="missing") == []
    assert t1.family_holiday_drift(d, calendar="../etc") == []


def test_holiday_calendars_match_published_2024_dates_and_are_current() -> None:
    nyse = eh.nyse(2024)
    assert {d.isoformat() for d in nyse} == {
        "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19",
        "2024-07-04", "2024-09-02", "2024-11-28", "2024-12-25"}
    assert {d.isoformat() for d in eh.lse(2024)} == {
        "2024-01-01", "2024-03-29", "2024-04-01", "2024-05-06", "2024-05-27", "2024-08-26",
        "2024-12-25", "2024-12-26"}
    jp = {d.isoformat() for d in eh.jpx(2024)}
    for want in ("2024-02-12", "2024-05-06", "2024-08-12", "2024-09-23", "2024-11-04"):
        assert want in jp, f"{want} is a JPX substitute holiday"
    assert {"2015-09-22", "2026-09-22"} <= {d.isoformat() for y in (2015, 2026)
                                            for d in eh.jpx(y)}
    assert eh.easter(2025).isoformat() == "2025-04-20"
    assert eh.write(check=True) == [], "regenerate: python desks/mt5/research/exchange_holidays.py"


def test_proposer_grid_is_declared_and_parks_absent_inputs_by_name(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(tp, "REPORT", tmp_path / "TIER1_IDEA_PROPOSER.json")
    monkeypatch.setattr(t1, "fred_series", lambda sid: None)
    by_id = {i["id"]: i for i in tp.ideas()}
    assert set(by_id) == {"U1", "U2", "U3", "U4", "U5", "U6", "N1"}
    assert len(tp.variants(by_id["U1"], "US500")) == 8
    assert tp.variants(by_id["N1"], "GER40")[0]["calendar"] == "xetra"
    u3 = tp.variants(by_id["U3"], "XTIUSD")
    assert len(u3) == 8 and all(v["implied_series"] == "OVXCLS" for v in u3)
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    doc = tp.run(only=["U3", "U6"], now=now)
    assert doc["ideas"]["U3"]["status"] == "PARKED"
    assert all("not yet in the world dataset store" in v
               for v in doc["ideas"]["U3"]["parked"].values())
    assert doc["ideas"]["U6"]["status"] == "PARKED", "U6 waits for first-release vintages"
    assert all(v == tp.U6_PARK for v in doc["ideas"]["U6"]["parked"].values())
    fresh = tp.run(now=now + timedelta(hours=2))
    assert fresh["status"] == "FRESH" and fresh["age_h"] == pytest.approx(2.0)
    assert tp.run(now=now + timedelta(hours=21), only=["U6"])["status"] == "SWEPT"


def test_the_cboe_reprints_stay_off_the_public_repo() -> None:
    """GVZCLS/OVXCLS are CBOE indices FRED reprints with permission: never committed."""
    import subprocess

    probe = "desks/mt5/data/world_datasets/obs/FRED/GVZCLS.parquet"
    out = subprocess.run(["git", "check-ignore", "-q", probe], cwd=ROOT, check=False)
    assert out.returncode == 0, f"{probe} must be gitignored"


def test_breadth_decision_is_never_before_the_last_share_open_it_used() -> None:
    """Share CFDs open at the cash bell (~16:30 broker); the index decides on or after that bar."""
    panel = {f"N{i}": _bars(days=200, seed=200 + i) for i in range(25)}
    for frame in panel.values():                       # share CFDs print only the cash session
        minute, _ = t1.LC.local_frame(frame.index, "America/New_York")
        keep = (minute >= 9 * 60 + 30) | ((minute < 9 * 60 + 30) & (minute + 60 > 9 * 60 + 30))
        frame.drop(frame.index[~(keep & (minute < 16 * 60))], inplace=True)
    b = t1.gap_breadth(panel, "America/New_York", "09:30", "16:00", gap_sd=0.5, vol_days=20,
                       min_names=20)
    assert not b.empty
    sigs = t1.family_equity_gap_breadth(_bars(days=200, seed=8), breadth=b, breadth_lo=0.0)
    assert sigs
    stamps = b.index
    for s in sigs:
        used = stamps[stamps <= s.time]
        assert len(used) and used[-1].normalize() == s.time.normalize()
        assert s.time >= used[-1], "decided before the share open it read"
