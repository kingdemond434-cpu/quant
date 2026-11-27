"""Bar-spread z (IDEA_QUEUE row 225): point-in-time minute-of-week baseline, the 1-point scale
floor, the forward 15-minute range, the gold_asia pre-trigger join, and UNMEASURED wherever
nothing was measured. EVERY BAR AND LEDGER ROW IS SYNTHETIC; nothing reads repo data."""

from __future__ import annotations

import json
import math
import sys as _sys
from pathlib import Path as _Path

import numpy as np
import pandas as pd

_DESK = _Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from research import bar_spread_z as bz  # noqa: E402

M1 = pd.Timedelta(minutes=1)


def _bars(start: str, n: int, spread=5, price=100.0, tz: str | None = "UTC") -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="min", tz=tz)
    sp = spread if np.ndim(spread) else np.full(n, spread)
    return pd.DataFrame({"open": price, "high": price + 0.5, "low": price - 0.5, "close": price,
                         "tick_volume": 10, "spread": np.asarray(sp, dtype="int32"),
                         "real_volume": 0}, index=idx.rename("timestamp"))


def _weekly(weeks: int, minutes: int = 30, base: int = 5) -> pd.DataFrame:
    """The same `minutes`-long Monday window for `weeks` weeks."""
    parts = [_bars(str(pd.Timestamp("2026-01-05 02:00") + pd.Timedelta(weeks=w)), minutes,
                   spread=base) for w in range(weeks)]
    return pd.concat(parts)


def test_minute_of_week_is_broker_wall_clock():
    idx = pd.DatetimeIndex(["2026-01-05 00:00", "2026-01-06 01:02"])  # Mon, Tue
    assert list(bz.minute_of_week(idx)) == [0, 1440 + 62]


def test_load_bars_keeps_wall_clock_and_drops_tz(tmp_path):
    b = _bars("2026-01-05 02:00", 3)
    b.to_parquet(tmp_path / "XAUUSD_M1.parquet")
    got, reason, trunc = bz.load_bars(tmp_path / "XAUUSD_M1.parquet", 10)
    assert reason is None and not trunc
    assert got.index.tz is None and got.index[0] == pd.Timestamp("2026-01-05 02:00")


def test_load_bars_missing_and_no_spread_are_reasons(tmp_path):
    assert bz.load_bars(tmp_path / "X_M1.parquet", 10)[1] == "X_M1.parquet absent"
    _bars("2026-01-05", 3).drop(columns="spread").to_parquet(tmp_path / "Y_M1.parquet")
    _, reason, _ = bz.load_bars(tmp_path / "Y_M1.parquet", 10)
    assert "spread" in reason


def test_load_bars_truncates_to_budget(tmp_path):
    _bars("2026-01-05", 50).to_parquet(tmp_path / "X_M1.parquet")
    got, _, trunc = bz.load_bars(tmp_path / "X_M1.parquet", 20)
    assert trunc and len(got) == 20 and got.index[-1] == pd.Timestamp("2026-01-05 00:49")


def test_z_is_point_in_time_and_floored():
    b = _weekly(6)
    # week 5 (index 5) widens to 9 points at its first minute
    pos = 5 * 30
    b.iloc[pos, b.columns.get_loc("spread")] = 9
    s = bz.spread_z(b.tz_localize(None), lookback=104, min_history=4)
    # weeks 0-3 have < 4 earlier same-minute bars -> no z (NaN, never 0)
    assert s["z"].iloc[: 4 * 30].isna().all()
    # week 4: four earlier 5s, median 5, IQR 0 -> floor 1 point, z = 0 exactly measured
    assert s["z"].iloc[4 * 30] == 0.0 and bool(s["floored"].iloc[4 * 30])
    # week 5's widened bar: z = (9 - 5) / 1
    assert s["z"].iloc[pos] == 4.0
    # the widened bar must not leak into its own baseline
    assert s["base_median"].iloc[pos] == 5.0


def test_z_uses_iqr_when_above_floor():
    vals = [2, 4, 6, 8, 10]
    b = pd.concat([_bars(str(pd.Timestamp("2026-01-05 02:00") + pd.Timedelta(weeks=w)), 1,
                         spread=v) for w, v in enumerate(vals)]).tz_localize(None)
    s = bz.spread_z(b, lookback=104, min_history=4)
    prior = pd.Series([2, 4, 6, 8], dtype=float)
    scale = (prior.quantile(0.75) - prior.quantile(0.25)) / 1.349
    assert math.isclose(s["z"].iloc[4], (10 - prior.median()) / scale)


def test_forward_range_requires_contiguous_bars():
    b = _bars("2026-01-05 00:00", 40, tz=None)
    b.iloc[20, b.columns.get_loc("high")] = 103.0
    r = bz.forward_range_bps(b)
    assert math.isclose(r.iloc[5], (103.0 - 99.5) / 100.0 * 1e4)
    assert r.iloc[40 - 15:].isna().all()
    gap = b.drop(b.index[10])
    rg = bz.forward_range_bps(gap)
    assert np.isnan(rg.iloc[0])  # bars 1..15 span a missing minute


def test_symbol_without_history_is_unmeasured_not_zero(tmp_path):
    _bars("2026-01-05", 60).to_parquet(tmp_path / "XAUUSD_M1.parquet")
    doc = bz.build(tmp_path, tmp_path / "none.jsonl", symbols=("XAUUSD", "EURUSD"))
    x = doc["symbols"]["XAUUSD"]
    assert x["status"] == "UNMEASURED" and x["n_z"] == 0
    assert doc["symbols"]["EURUSD"]["reason"] == "EURUSD_M1.parquet absent"
    assert doc["gold_asia_pre_trigger"]["status"] == "UNMEASURED"
    assert doc["gold_asia_pre_trigger"]["reason"] == "live ledger absent"
    assert doc["status"] == "UNMEASURED"
    assert doc["bar_clock"] == "broker (NY+7)"


def _ledger(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_gold_asia_join_and_scrub(tmp_path):
    weeks = 6
    _weekly(weeks).to_parquet(tmp_path / "XAUUSD_M1.parquet")
    rows = []
    for w in range(4, weeks):
        t = pd.Timestamp("2026-01-05 02:20") + pd.Timedelta(weeks=w)
        rows.append({"sleeve": "gold_asia", "symbol": "XAUUSD", "entry_time":
                     t.isoformat() + "+00:00", "timestamp_basis": "broker_deal_epoch",
                     "r_multiple": 0.5 * w, "account": 5551234, "login": 5551234,
                     "deal": 99999999})
    rows.append({"sleeve": "gold_asia", "symbol": "XAUUSD", "r_multiple": 1.0})  # no entry
    rows.append({"sleeve": "gold_asia", "symbol": "XAUUSD", "entry_time": "2026-02-09T02:20:00",
                 "timestamp_basis": "local", "r_multiple": 1.0})
    rows.append({"sleeve": "other", "symbol": "XAUUSD", "entry_time": "2026-02-09T02:20:00",
                 "timestamp_basis": "broker_deal_epoch", "r_multiple": 1.0})
    _ledger(tmp_path / "live_ledger.jsonl", rows)
    doc = bz.build(tmp_path, tmp_path / "live_ledger.jsonl", symbols=("XAUUSD",), min_legs=2)
    g = doc["gold_asia_pre_trigger"]
    assert g["n_legs"] == 2 and g["n_joined"] == 2
    assert g["skipped"]["no_entry_time"] == 1
    assert g["skipped"]["clock_not_broker_deal_epoch"] == 1
    assert g["legs"][0]["entry_broker"] == "2026-02-02T02:20"
    assert g["legs"][0]["z_pre_max"] == 0.0 and g["legs"][0]["n_pre_bars"] == 5
    assert g["status"] == "MEASURED"
    text = json.dumps(doc)
    assert "5551234" not in text and "99999999" not in text
    assert '"account"' not in text and '"login"' not in text
    assert "+00:00" not in json.dumps(g)


def test_gold_asia_leg_outside_bars_is_unmeasured_with_reason(tmp_path):
    _weekly(6).to_parquet(tmp_path / "XAUUSD_M1.parquet")
    _ledger(tmp_path / "l.jsonl", [{"sleeve": "gold_asia", "symbol": "XAUUSD",
                                     "entry_time": "2027-01-01T00:00:00+00:00",
                                     "timestamp_basis": "broker_deal_epoch",
                                     "r_multiple": -1.0}])
    g = bz.build(tmp_path, tmp_path / "l.jsonl", symbols=("XAUUSD",))["gold_asia_pre_trigger"]
    assert g["legs"][0]["z_pre_max"] == "UNMEASURED"
    assert g["legs"][0]["reason"] == "trigger outside the held bars"
    assert g["status"] == "UNMEASURED" and "need 10" in g["reason"]


def test_next15_buckets_and_spearman(tmp_path):
    b = _weekly(12, minutes=60)
    rng = np.random.default_rng(0)
    # spread changes in 20-minute blocks, so forward 15-minute windows see different ranges
    sp = np.repeat(5 + rng.integers(0, 4, len(b) // 20 + 1), 20)[: len(b)]
    b["spread"] = sp.astype("int32")
    # make range grow with spread so the rank correlation is positive
    b["high"] = b["close"] + sp * 0.1
    b["low"] = b["close"] - sp * 0.1
    b.to_parquet(tmp_path / "EURUSD_M1.parquet")
    doc = bz.build(tmp_path, tmp_path / "none.jsonl", symbols=("EURUSD",))
    n15 = doc["symbols"]["EURUSD"]["next15_range"]
    assert n15["status"] == "MEASURED" and n15["n_pairs"] > 0
    assert isinstance(n15["spearman_z_vs_range"], float)
    assert set(n15["by_z_bucket"]) == {"z<1", "1<=z<2", "z>=2"}


def test_time_budget_marks_remaining_symbols(tmp_path):
    doc = bz.build(tmp_path, tmp_path / "none.jsonl", symbols=("XAUUSD", "EURUSD"),
                   time_budget_s=-1.0)
    assert doc["budget"]["exceeded"] is True
    assert all(s["status"] == "UNMEASURED" for s in doc["symbols"].values())


def test_main_writes_report(tmp_path):
    out = tmp_path / "r" / "bar_spread_z.json"
    assert bz.main(["--universe", str(tmp_path), "--ledger", str(tmp_path / "n.jsonl"),
                    "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["report_only"] is True and doc["veto_wired"] is False
