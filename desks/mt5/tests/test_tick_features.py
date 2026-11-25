"""TICK_FEATURES: point-in-time tape conditioners -- no look-ahead, the three features, the
exotic ban, UNMEASURED on no tape, the lake shape exogenous_conditioner reads, and the leg wiring.

Inputs are CSV written under `.parquet` names with `pandas.read_parquet` pointed at `read_csv`, so
the REAL tape reader (`moat_series.tape_index` + `moat_series._read_day`) runs on them.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import moat_series as mos  # noqa: E402
from research import tick_features as tf  # noqa: E402
from research import universe_policy as up  # noqa: E402

DAY0 = datetime(2026, 11, 2, tzinfo=UTC)
DAY0_MS = int(DAY0.timestamp() * 1000)
NOW = datetime(2026, 11, 20, tzinfo=UTC)
EVENT_DAY, EVENT_HOUR, EVENT_MIN = 6, 13, 30


def _csv_parquet(path: Any, columns: Any = None, **_k: Any) -> pd.DataFrame:
    return pd.read_csv(path, usecols=columns)


def _ticks(day: int, *, hours: int = 24, spread_bps: float | None = None,
           shock_at_ms: int | None = None, wide_from_hour: int | None = None,
           thin: bool = False) -> pd.DataFrame:
    """One tick a minute (at :07 s) for `hours` hours of day `day`. The spread varies by day and
    hour unless fixed; a shock lifts the mid 20 bps and the spread to 3 bps for 15 minutes;
    `wide_from_hour` sets 9 bps from that hour on; `thin` drops some minutes so the arrival rate
    varies by day and hour."""
    start = DAY0_MS + day * tf.DAY_MS
    ms = start + np.arange(0, hours * 60, dtype="int64") * tf.MIN_MS + 7_000
    minute = (ms // tf.MIN_MS).astype(float)
    mid = 1.1 * (1.0 + 3e-4 * np.sin(minute / 7.0) + 1e-4 * np.cos(minute / 3.0))
    hour = (ms // tf.HOUR_MS) % 24
    sp = (np.full(ms.size, spread_bps) if spread_bps is not None
          else 1.0 + 0.5 * np.sin(hour * 1.3 + day * 0.7) ** 2)
    if wide_from_hour is not None:
        sp = np.where(hour >= wide_from_hour, 9.0, sp)
    if shock_at_ms is not None:
        after = ms >= shock_at_ms
        mid = np.where(after, mid * 1.002, mid)
        sp = np.where(after & (ms < shock_at_ms + 15 * tf.MIN_MS), 3.0, sp)
    half = mid * sp * 1e-4 / 2.0
    frame = pd.DataFrame({"time_msc": ms, "bid": mid - half, "ask": mid + half})
    if thin:
        k = np.arange(ms.size)
        frame = frame[~(((k + day * 5 + hour) % 4 == 0) & ((day + hour) % 3 == 0))]
    return frame


def _day_name(day: int) -> str:
    return datetime.fromtimestamp((DAY0_MS + day * tf.DAY_MS) / 1000, tz=UTC).date().isoformat()


def _write_day(ticks: Path, sym: str, day: int, frame: pd.DataFrame) -> None:
    p = ticks / sym / f"{_day_name(day)}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(p, index=False)


def _event_ms() -> int:
    return DAY0_MS + EVENT_DAY * tf.DAY_MS + EVENT_HOUR * tf.HOUR_MS + EVENT_MIN * tf.MIN_MS


def _desk(tmp: Path, monkeypatch: Any, *,
          universe: dict[str, Any] | None = None) -> dict[str, Path]:
    ticks = tmp / "ticks"
    ticks.mkdir(parents=True, exist_ok=True)
    uni = tmp / "universe.json"
    uni.write_text(json.dumps(universe or {
        "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
        "USDNOK": {"asset_class": "Forex", "currency_profit": "NOK"},
        "XAUUSD": {"asset_class": "Metals", "currency_profit": "USD"}}), encoding="utf-8")
    monkeypatch.setattr(mos, "TICKS", ticks)
    monkeypatch.setattr(up, "UNIVERSE", uni)
    monkeypatch.setattr(pd, "read_parquet", _csv_parquet)
    vint = tmp / "vintage"
    vint.mkdir()
    t = datetime.fromtimestamp(_event_ms() / 1000, tz=UTC).isoformat()
    (vint / "discoveries_1.json").write_text(json.dumps([
        {"title": "USD CPI m/m", "symbols": ["USD"], "event_date": t, "impact": "High"},
        {"title": "USD Low thing", "symbols": ["USD"], "event_date": t, "impact": "Low"},
        {"title": "USD Bank Holiday", "symbols": ["USD"], "event_date": "2026-11-05",
         "impact": "High"}]), encoding="utf-8")
    return {"ticks": ticks, "series": tmp / "series", "store": tmp / "store", "vintage": vint}


def _build(paths: dict[str, Path], **kw: Any) -> dict[str, Any]:
    return tf.build(budget_s=60, now=NOW, series_dir=paths["series"], store=paths["store"],
                    vintage_dir=paths["vintage"], extra_calendars=False, **kw)


def _frame(paths: dict[str, Path], name: str) -> pd.DataFrame:
    return pd.read_csv(paths["series"] / f"{name}.csv")


# ------------------------------------------------------------------------------ look-ahead --
def test_a_future_tick_never_changes_a_past_row(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _desk(tmp_path, monkeypatch)
    for d in range(7):
        _write_day(paths["ticks"], "EURUSD", d,
                   _ticks(d, shock_at_ms=_event_ms() if d == EVENT_DAY else None))
    _write_day(paths["ticks"], "EURUSD", 7, _ticks(7, hours=12))     # day 7 still recording
    _build(paths)
    first = _frame(paths, "tick_features_EURUSD")
    news_first = _frame(paths, "tick_news_EURUSD")
    # an hour still being recorded is never published half-built
    assert first["available_time"].max() <= datetime.fromtimestamp(
        (DAY0_MS + 7 * tf.DAY_MS + 11 * tf.HOUR_MS) / 1000, tz=UTC).isoformat()

    # the rest of day 7 and all of day 8 arrive, with a wild spread regime
    _write_day(paths["ticks"], "EURUSD", 7, _ticks(7, wide_from_hour=12))
    _write_day(paths["ticks"], "EURUSD", 8, _ticks(8, spread_bps=9.0))
    _build(paths)
    second = _frame(paths, "tick_features_EURUSD")
    assert len(second) > len(first)
    pd.testing.assert_frame_equal(second.iloc[:len(first)].reset_index(drop=True), first)
    pd.testing.assert_frame_equal(_frame(paths, "tick_news_EURUSD"), news_first)
    # the new hours ARE different, so the comparison above was not vacuous
    assert second["spread_bps"].iloc[-1] > first["spread_bps"].max()
    # every row is stamped strictly after the hour it summarises
    ev = pd.to_datetime(second["event_time"], utc=True)
    av = pd.to_datetime(second["available_time"], utc=True)
    assert ((av - ev) == pd.Timedelta(hours=1)).all()


def test_moves_inside_an_hour_never_reach_past_its_end() -> None:
    ms = DAY0_MS + np.arange(0, 120, dtype="int64") * tf.MIN_MS + 1_000
    mid = np.where(ms >= DAY0_MS + tf.HOUR_MS, 2.0, 1.0)       # a jump exactly at the boundary
    d = {"ms": ms, "mid": mid, "spread_bps": np.ones(ms.size)}
    rows = tf.hour_rows("d", d)
    assert rows[0]["mv5"] == 0.0 and rows[0]["mv15"] == 0.0
    assert rows[0]["mid_last"] == 1.0


# ------------------------------------------------------------------------- spread regime --
def test_spread_regime_percentile_against_strictly_earlier_hours() -> None:
    n = 80
    h = pd.DataFrame({"hour_ms": DAY0_MS + np.arange(n) * tf.HOUR_MS,
                      "spread_bps": np.arange(1.0, n + 1.0)})
    h.loc[n - 1, "spread_bps"] = 0.5                           # the tightest hour on record
    pct, state = tf.spread_regime(h)
    assert np.isnan(pct[: tf.REGIME_MIN_OBS]).all()            # too little history: UNMEASURED
    assert pct[tf.REGIME_MIN_OBS] == 1.0 and state[tf.REGIME_MIN_OBS] == 1.0   # widest yet
    assert pct[n - 1] == 0.0 and state[n - 1] == -1.0
    # a mid-ranked hour reads normal, ties counted half
    h2 = pd.DataFrame({"hour_ms": DAY0_MS + np.arange(60) * tf.HOUR_MS,
                       "spread_bps": [1.0, 2.0] * 30})
    pct2, state2 = tf.spread_regime(h2)
    assert math.isclose(pct2[59], (30 + 0.5 * 29) / 59)
    assert state2[59] == 0.0


# ---------------------------------------------------------------------- liquidity by hour --
def test_hour_profile_is_the_median_of_strictly_earlier_days() -> None:
    days = 9
    t = np.array([DAY0_MS + d * tf.DAY_MS + 10 * tf.HOUR_MS for d in range(days)])
    h = pd.DataFrame({"hour_ms": t, "hod": 10, "tick_rate": np.arange(1.0, days + 1),
                      "spread_bps": 1.0, "mv5": 1.0, "mv15": 1.0, "mv60": 1.0})
    prof = tf.hour_profile(h)
    assert np.isnan(prof["tick_rate"][: tf.PROFILE_MIN_OBS]).all()
    assert prof["tick_rate"][5] == 3.0                         # median of days 1..5
    assert prof["tick_rate"][8] == 4.5                         # median of days 1..8
    h["n"] = h["tick_rate"] * 60
    h["last_ms"] = h["hour_ms"] + tf.HOUR_MS
    hs, _ = tf.hourly_series(h.assign(zero_spread_frac=0.0), float(t[-1] + 2 * tf.HOUR_MS))
    assert math.isclose(hs["tick_rate_dev"].iloc[8], math.log(9.0 / 4.5))


def test_report_carries_the_profile_and_todays_deviation(tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    paths = _desk(tmp_path, monkeypatch)
    for d in range(8):
        _write_day(paths["ticks"], "EURUSD", d, _ticks(d))
    today = datetime.fromtimestamp((DAY0_MS + 7 * tf.DAY_MS) / 1000 + 86_000, tz=UTC)
    doc = tf.build(budget_s=60, now=today, series_dir=paths["series"], store=paths["store"],
                   vintage_dir=paths["vintage"], extra_calendars=False)
    liq = doc["symbols"]["EURUSD"]["features"]["liquidity_by_hour"]
    assert liq["status"] == tf.MEASURED
    assert set(liq["profile_by_utc_hour"]) == {str(k) for k in range(24)}
    assert math.isclose(liq["profile_by_utc_hour"]["10"]["tick_rate"], 1.0)   # 60 ticks/hour
    assert liq["today_deviation"]["10"]["tick_rate_dev"] == 0.0


# ------------------------------------------------------------------------------- post-news --
def test_post_news_response_against_the_symbols_baseline(tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    paths = _desk(tmp_path, monkeypatch)
    for d in range(8):
        _write_day(paths["ticks"], "EURUSD", d,
                   _ticks(d, spread_bps=1.0,
                          shock_at_ms=_event_ms() if d == EVENT_DAY else None))
    doc = _build(paths)
    cal = doc["calendar"]
    assert cal["low_or_holiday"] == 1 and cal["day_precision_or_unparsed"] == 1
    news = _frame(paths, "tick_news_EURUSD")
    assert len(news) == 1
    row = news.iloc[0]
    assert row["event"] == "USD CPI m/m" and row["currency"] == "USD"
    # known at the end of the longest window, never at the release
    t = pd.Timestamp(_event_ms(), unit="ms", tz="UTC")
    assert pd.Timestamp(row["event_time"]) == t
    assert pd.Timestamp(row["available_time"]) == t + pd.Timedelta(minutes=60)
    # spread 3 bps inside 15 min against a 1 bps profile; back to 1 bps over the hour
    assert math.isclose(row["spread_widen_5m"], 3.0, rel_tol=1e-6)
    assert math.isclose(row["spread_widen_15m"], 3.0, rel_tol=1e-6)
    assert row["spread_widen_60m"] < row["spread_widen_15m"]
    assert row["move_bps_5m"] > 15.0 and row["move_signed_bps_15m"] > 15.0
    # the ratio is the move over the hour's trailing typical move -- built from EARLIER days only
    h = tf.hourly_base(pd.read_csv(paths["store"] / "hourly" / "EURUSD.csv"))
    prof = tf.hour_profile(h)
    i = int(np.where(h["hour_ms"].to_numpy() == (_event_ms() // tf.HOUR_MS) * tf.HOUR_MS)[0][0])
    assert math.isclose(row["move_ratio_5m"], row["move_bps_5m"] / prof["mv5"][i], rel_tol=1e-9)
    assert row["move_ratio_5m"] > 5.0
    assert doc["symbols"]["EURUSD"]["features"]["post_news"]["status"] == tf.MEASURED


# ------------------------------------------------------------------- exotics and absence --
def test_exotics_are_excluded_and_no_tape_is_unmeasured(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _desk(tmp_path, monkeypatch)
    for d in range(3):
        _write_day(paths["ticks"], "EURUSD", d, _ticks(d))
        _write_day(paths["ticks"], "USDNOK", d, _ticks(d))
    doc = _build(paths)
    assert "USDNOK" in doc["exotics_set_aside"]
    assert "USDNOK" not in doc["symbols"]
    assert not (paths["series"] / "tick_features_USDNOK.csv").exists()
    assert not (paths["store"] / "hourly" / "USDNOK.csv").exists()
    xau = doc["symbols"]["XAUUSD"]
    assert xau["status"] == tf.UNMEASURED and "no tape" in xau["why"]
    assert all(v["status"] == tf.UNMEASURED for v in xau["features"].values())
    assert doc["symbols_unmeasured"] >= 1 and doc["symbols_measured"] == 1
    assert doc["coverage"]["spread_regime"]["unmeasured"] >= 1
    # three days cannot rank a spread against 48 earlier hours: UNMEASURED, never a zero
    reg = doc["symbols"]["EURUSD"]["features"]["spread_regime"]
    assert reg["status"] == tf.MEASURED or reg["measured_rows"] == 0
    hs = _frame(paths, "tick_features_EURUSD")
    assert hs["spread_pctile"].iloc[:tf.REGIME_MIN_OBS].isna().all()


def test_an_empty_desk_reads_unmeasured_not_zero(tmp_path: Path, monkeypatch: Any) -> None:
    paths = _desk(tmp_path, monkeypatch)
    doc = _build(paths)
    assert doc["status"] == tf.UNMEASURED
    assert doc["symbols_measured"] == 0 and doc["series_published"] == 0
    assert all(v["status"] == tf.UNMEASURED for v in doc["symbols"].values())


# ------------------------------------------------------------- the shape the path reads --
def test_series_are_in_the_shape_exogenous_conditioner_reads(tmp_path: Path,
                                                             monkeypatch: Any) -> None:
    paths = _desk(tmp_path, monkeypatch)
    for d in range(8):
        _write_day(paths["ticks"], "EURUSD", d, _ticks(d, thin=True))
    _build(paths)
    from mt5desk import family_exogenous_conditioner as fec
    frame = _frame(paths, "tick_features_EURUSD")
    assert {"event_time", "available_time", "source_id"} <= set(frame.columns)
    assert set(tf.HOURLY_COLUMNS) <= set(frame.columns)
    signals = [c for c in frame.columns if c not in fec.STAMP_COLUMNS]
    assert set(signals) == set(tf.HOURLY_COLUMNS)              # every non-stamp column a number
    for sig in ("spread_pctile", "tick_rate_dev", "spread_hour_dev"):
        s = fec.conditioner("tick_features_EURUSD", sig, "level_z", root=paths["series"],
                            lag_hours=tf.MIN_CONDITIONER_LAG_HOURS)
        assert s is not None and len(s) > 0, sig
    # the lag the family applies holds the value back past its own knowledge stamp
    raw = fec.conditioner("tick_features_EURUSD", "tick_rate", "delta", root=paths["series"],
                          lag_hours=tf.MIN_CONDITIONER_LAG_HOURS)
    assert raw is not None
    first_known = pd.to_datetime(frame["available_time"], utc=True).min()
    assert raw.index.min() >= first_known + pd.Timedelta(hours=tf.MIN_CONDITIONER_LAG_HOURS)
    # the source-conversion yield rule sees each file as a lake series
    from research import source_conversion as sc
    desk = tmp_path / "desk"
    (desk / "data" / "lake").mkdir(parents=True)
    (desk / "data" / "lake" / "series").symlink_to(paths["series"], target_is_directory=True)
    assert sc.existing_sources(desk).get("tick_features_EURUSD") == "lake_series"


# ------------------------------------------------------------------------------ the wiring --
def _load(name: str, rel: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_is_an_hourly_leg_in_every_registry() -> None:
    hc = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert 'tkf = _costed("tick_features", lambda: _producer("tick_features", ' \
           '"research/tick_features.py",' in hc
    assert '"tick_features": tkf' in hc
    from research import hourly_cycle as hcm
    assert hcm.department_of("tick_features") == "data"
    assert hcm.LEG_BUDGET_SEC["tick_features"] > 240
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["tick_features"] == "information"
    from libs.tiers import experiment_contract as ec
    reg = json.loads((ROOT / "docs/research/experiment_contracts.json").read_text("utf-8"))
    c = reg["legs"]["tick_features"]
    assert ec.problems({**c, "budget": {"seconds": 300}, "owner": "data"}) == []
    assert c["metric"]["organ"] == "report:TICK_FEATURES.json"
    oc = _load("organ_contract_tick", "ops/organ_contract.py")
    assert oc.CONTRACTS["MT5-Hourly (tick features)"][0] == "desks/mt5/reports/TICK_FEATURES.json"
    from libs.tiers import data_os
    assert "desks/mt5/research/tick_features.py" in data_os.READER_ROUTES
    lag = data_os.PUBLICATION_LAGS["tick_features"]
    assert lag["knowledge_column"] == "available_time" and lag["lag_s"] == 0


def test_a_tick_source_below_the_utc_floor_is_raised_to_it() -> None:
    """Audit HOLD 2026-11-25: lag 0 on a UTC tape source would look ahead into broker-time bars."""
    from mt5desk import family_exogenous_conditioner as fx
    assert fx.effective_lag_hours("tick_features_EURUSD", 0) == fx.UTC_TAPE_MIN_LAG_HOURS
    assert fx.effective_lag_hours("tick_news_XAUUSD", 1) == fx.UTC_TAPE_MIN_LAG_HOURS
    assert fx.effective_lag_hours("tick_features_EURUSD", 24) == 24
    assert fx.effective_lag_hours("fred_DGS10", 0) == 0          # other sources unchanged
    assert fx.UTC_TAPE_MIN_LAG_HOURS == tf.MIN_CONDITIONER_LAG_HOURS
