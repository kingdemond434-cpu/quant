"""Bar illiquidity (IDEA_QUEUE row 218): Corwin-Schultz against a closed-form answer, the
tick-volume Amihud and Kyle proxies against hand arithmetic, z-scores against the hour's own
past only, and UNMEASURED wherever nothing was measured.

EVERY BAR IS SYNTHETIC; nothing here reads the repo's charts, the tape or the network.

THE KNOWN ANSWER. Two adjacent bars with the SAME range [L, H] and no gap give
beta = 2a^2, gamma = a^2 with a = ln(H/L); since sqrt(k) = sqrt(2) - 1 for k = 3 - 2*sqrt(2),
alpha collapses to exactly a, so S = 2*(H/L - 1)/(1 + H/L). For H=101, L=100: S = 0.02/2.01.
"""

from __future__ import annotations

import json
import math
import sys as _sys
from datetime import UTC, datetime
from pathlib import Path as _Path

import numpy as np
import pandas as pd
import pytest

_DESK = _Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from research import bar_illiquidity as bi  # noqa: E402

M1 = pd.Timedelta(minutes=1)


def _frame(idx, high, low, close, ticks):
    return pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": ticks,
            "spread": 5,
            "real_volume": 0,
        },
        index=pd.DatetimeIndex(idx),
    )


def _synthetic(days=15, *, seed=0, wide_last_hour=None, widen=1.0, start="2026-09-01"):
    """M1 bars, days x 24h, random walk; optionally the LAST day's `wide_last_hour` ranges
    are multiplied by `widen`."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24 * 60, freq="1min", tz="UTC")
    r = rng.normal(0, 2e-4, len(idx))
    close = 100 * np.exp(np.cumsum(r))
    half = np.full(len(idx), 1e-4)
    if wide_last_hour is not None:
        last_day = idx[-1].normalize()
        mask = (idx >= last_day + pd.Timedelta(hours=wide_last_hour)) & (
            idx < last_day + pd.Timedelta(hours=wide_last_hour + 1)
        )
        half[mask] *= widen
    high = close * (1 + half + np.abs(r))
    low = close * (1 - half - np.abs(r))
    ticks = rng.integers(20, 200, len(idx))
    return _frame(idx, high, low, close, ticks)


# ---------------------------------------------------------------------------- Corwin-Schultz


def test_corwin_schultz_known_answer():
    idx = pd.date_range("2026-09-01", periods=2, freq="1min", tz="UTC")
    bars = _frame(idx, [101.0, 101.0], [100.0, 100.0], [100.5, 100.5], [10, 10])
    cs = bi.corwin_schultz_pairs(bars, M1)
    assert len(cs) == 1
    assert cs["s_raw"].iloc[0] == pytest.approx(0.02 / 2.01, rel=1e-12)
    assert cs["s"].iloc[0] == pytest.approx(0.009950248756218905, rel=1e-12)


def test_corwin_schultz_known_answer_general_range():
    h_over_l = 1.0037
    idx = pd.date_range("2026-09-01", periods=2, freq="1min", tz="UTC")
    bars = _frame(idx, [50 * h_over_l] * 2, [50.0] * 2, [50.05] * 2, [10, 10])
    s = bi.corwin_schultz_pairs(bars, M1)["s"].iloc[0]
    assert s == pytest.approx(2 * (h_over_l - 1) / (1 + h_over_l), rel=1e-10)


def test_corwin_schultz_negative_is_clipped_and_kept_raw():
    # a large move between two narrow bars -> gamma dominates -> alpha < 0
    idx = pd.date_range("2026-09-01", periods=2, freq="1min", tz="UTC")
    bars = _frame(idx, [100.1, 100.6], [100.0, 100.5], [100.55, 100.55], [10, 10])
    cs = bi.corwin_schultz_pairs(bars, M1)
    assert cs["s_raw"].iloc[0] < 0
    assert cs["s"].iloc[0] == 0.0


def test_corwin_schultz_gap_adjustment_shifts_onto_previous_close():
    # bar 2 gapped wholly above close[0]; after adjustment it equals bar 1's range -> known answer
    idx = pd.date_range("2026-09-01", periods=2, freq="1min", tz="UTC")
    bars = _frame(idx, [101.0, 106.0], [100.0, 105.0], [100.0, 105.5], [10, 10])
    # gap = 105 - 100 = 5 -> [100, 101]
    assert bi.corwin_schultz_pairs(bars, M1)["s"].iloc[0] == pytest.approx(0.02 / 2.01)


def test_corwin_schultz_skips_non_adjacent_pairs():
    idx = pd.DatetimeIndex(["2026-09-01 00:00", "2026-09-01 00:05"], tz="UTC")
    bars = _frame(idx, [101.0, 101.0], [100.0, 100.0], [100.5, 100.5], [10, 10])
    assert bi.corwin_schultz_pairs(bars, M1).empty


# ------------------------------------------------------------------------- Amihud and Kyle


def test_amihud_and_kyle_hand_arithmetic():
    idx = pd.date_range("2026-09-01", periods=3, freq="1min", tz="UTC")
    close = [100.0, 101.0, 100.0]
    bars = _frame(idx, close, close, close, [5, 4, 9])
    fl = bi.bar_flow(bars, M1)
    r1, r2 = math.log(1.01), math.log(100 / 101)
    assert fl["amihud"].tolist() == pytest.approx([abs(r1) / 4, abs(r2) / 9])
    assert fl["sv"].tolist() == pytest.approx([2.0, -3.0])
    lam = bi._kyle(fl)
    assert lam == pytest.approx((2 * r1 + -3 * r2) / 13)


def test_zero_tick_bars_are_skipped_not_counted_as_zero():
    idx = pd.date_range("2026-09-01", periods=3, freq="1min", tz="UTC")
    close = [100.0, 101.0, 100.0]
    fl = bi.bar_flow(_frame(idx, close, close, close, [5, 0, 9]), M1)
    assert len(fl) == 1


# ------------------------------------------------------------------- z-scores, point in time


def test_wide_hour_scores_a_high_cs_z_against_its_own_history():
    bars = _synthetic(days=15, wide_last_hour=3, widen=6.0)
    as_of = pd.Timestamp(bars.index[-1]) + M1
    res = bi.analyse(bars, "M1", as_of, min_history=10, now=as_of.to_pydatetime())
    h3, h4 = res["hours"]["03"], res["hours"]["04"]
    assert h3["cs_spread"]["n_history"] == 14
    assert h3["cs_spread"]["z"] > 5
    assert abs(h4["cs_spread"]["z"]) < 4


def test_no_lookahead_future_bars_never_change_the_reading():
    base = _synthetic(days=15, seed=1)
    as_of = pd.Timestamp("2026-09-14T12:00:00Z")
    now = datetime(2026, 9, 14, 12, tzinfo=UTC)
    a = bi.analyse(base, "M1", as_of, now=now)
    future = base[base.index > as_of].copy()
    future[["high"]] *= 1.05
    future["tick_volume"] = 1
    poisoned = pd.concat([base[base.index <= as_of], future])
    b = bi.analyse(poisoned, "M1", as_of, now=now)
    assert a == b
    assert all(
        pd.Timestamp(h["bucket_start_utc"]) + pd.Timedelta(hours=1) <= as_of
        for h in a["hours"].values()
    )


def test_short_history_is_unmeasured_never_zero():
    bars = _synthetic(days=3)
    as_of = pd.Timestamp(bars.index[-1]) + M1
    res = bi.analyse(bars, "M1", as_of, min_history=10, now=as_of.to_pydatetime())
    for hour in res["hours"].values():
        for m in bi.MEASURES:
            assert hour[m]["z"] == "UNMEASURED"
            assert hour[m]["n_history"] == 2


def test_freshness_stamps_and_stale_flag():
    bars = _synthetic(days=12)
    last = pd.Timestamp(bars.index[-1])
    res = bi.analyse(bars, "M1", last + M1, now=(last + pd.Timedelta(hours=72)).to_pydatetime())
    f = res["freshness"]
    assert f["last_bar_utc"] == last.isoformat() and f["n_bars"] == len(bars)
    assert f["stale"] is True and res["status"] == "STALE"
    fresh = bi.analyse(bars, "M1", last + M1, now=(last + pd.Timedelta(hours=1)).to_pydatetime())
    assert fresh["status"] == "OK"


# ------------------------------------------------------------------------------- build / main


def test_no_bars_anywhere_is_unmeasured(tmp_path):
    doc = bi.build(tmp_path, now=datetime(2026, 10, 21, tzinfo=UTC))
    assert doc["status"] == "UNMEASURED" and doc["symbols"] == "UNMEASURED"


def test_main_reads_m1_and_m5_parquet_and_writes_report(tmp_path):
    m1 = _synthetic(days=12)
    m1.index.name = "timestamp"
    m1.to_parquet(tmp_path / "TEST_M1.parquet")
    m5 = m1.resample("5min").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "tick_volume": "sum",
            "spread": "last",
            "real_volume": "sum",
        }
    )
    m5.to_parquet(tmp_path / "TEST_M5.parquet")
    (tmp_path / "TEST_H1.parquet").write_bytes(b"ignored")
    out = tmp_path / "BAR_ILLIQUIDITY.json"
    assert (
        bi.main(["--universe", str(tmp_path), "--out", str(out), "--as-of", "2026-09-12T23:59:00Z"])
        == 0
    )
    doc = json.loads(out.read_text("utf-8"))
    assert set(doc["symbols"]) == {"TEST"}
    assert set(doc["symbols"]["TEST"]) == {"M1", "M5"}
    assert doc["symbols"]["TEST"]["M5"]["hours"]["10"]["cs_spread"]["z"] != "UNMEASURED"
