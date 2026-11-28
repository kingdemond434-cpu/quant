"""Survival inputs: Hill/POT tail index, the tail's cost in growth-optimal size, and the
microstructure-noise ratio / signature plot -- against synthetic data with known truth."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.risk import microstructure_noise as mn  # noqa: E402
from libs.risk import tail_index as ti  # noqa: E402


def _t(df: float, n: int = 3000, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).standard_t(df, n)


def test_hill_orders_tails_and_brackets_truth() -> None:
    a3 = np.mean([ti.hill(-_t(3, seed=s), boot=0)["alpha"] for s in range(6)])
    a5 = np.mean([ti.hill(-_t(5, seed=s), boot=0)["alpha"] for s in range(6)])
    assert 2.3 < a3 < 3.5
    assert a5 > a3 + 0.5


def test_pot_shape_matches_student_t() -> None:
    p = ti.pot(-_t(3, n=20000, seed=1))
    assert p["xi"] == pytest.approx(1 / 3, abs=0.12)
    assert p["es995"] > p["var995"] > p["var990"]


def test_gpd_tail_is_fatter_than_gaussian_for_t3() -> None:
    m = ti.measure(0.0005 + 0.01 * _t(3) / np.sqrt(3), rng=np.random.default_rng(0), boot=50)
    assert m is not None and m.es995_ratio is not None and m.es995_ratio > 1.2


def test_kelly_ratio_is_two_sided() -> None:
    rng = np.random.default_rng(4)
    fat = 0.0005 + 0.01 * rng.standard_t(3, 4000) / np.sqrt(3)
    stopped = np.clip(0.0005 + 0.01 * rng.standard_normal(4000), -0.008, None)
    _g1, _s1, r_fat = ti.kelly_ratio(fat, rng, 50_000)
    _g2, _s2, r_stop = ti.kelly_ratio(stopped, rng, 50_000)
    assert r_fat is not None and r_fat < 0.8          # fat losses cost growth-optimal size
    assert r_stop is not None and r_stop > 1.0        # truncated losses earn more than mu/s^2


def test_no_edge_has_no_ratio_and_short_series_no_reading() -> None:
    assert ti.kelly_ratio(-0.001 + 0.01 * _t(4))[2] is None
    assert ti.measure(np.zeros(50)) is None


def _tick_day(seed: int, n: int = 20000, sig: float = 0.006, om: float = 2e-5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.Timestamp("2026-11-02", tz="UTC") + pd.to_timedelta(
        np.sort(rng.uniform(0, 86400, n)), unit="s")
    p = np.cumsum(rng.normal(0, sig / np.sqrt(n), n)) + np.log(1.1)
    m = np.exp(p + rng.normal(0, om, n))
    return pd.DataFrame({"ts": ts, "bid": m * (1 - 3e-5), "ask": m * (1 + 3e-5)})


def test_noise_variance_tsrv_and_roll_recover_truth() -> None:
    out = mn.pool(mn.day_reading(_tick_day(s)) for s in range(5))
    assert out["status"] == "MEASURED"
    assert out["omega2"] == pytest.approx((2e-5) ** 2, rel=0.35)
    assert out["iv_tsrv"] == pytest.approx(0.006 ** 2, rel=0.2)
    assert out["roll_spread_rel"] == pytest.approx(2 * 2e-5, rel=0.25)
    sig = out["signature"]
    assert sig["5"] > sig["3600"]                 # the signature plot rises at short intervals
    # truth: noise share 2 n(D) omega^2 / RV(D) is ~11% at 15 s and ~6% at 30 s for this day
    assert out["min_horizon_s"] == 30


def test_noise_free_price_has_flat_signature() -> None:
    out = mn.pool(mn.day_reading(_tick_day(s, om=0.0)) for s in range(3))
    assert abs(out["signature_slope"]) < 0.1
    assert out["min_horizon_s"] == mn.GRID_S[0]


def test_bars_only_fallback_is_labelled() -> None:
    rng = np.random.default_rng(1)
    closes = np.exp(np.cumsum(rng.normal(0, 1e-4, 5000)) + rng.normal(0, 3e-5, 5000))
    r = mn.from_bars(closes)
    assert r["status"] == "BARS_ONLY" and r["lag1_autocorr"] < 0


def test_lab_end_to_end(tmp_path: Path) -> None:
    import survival_inputs_lab as lab

    uni = tmp_path / "universe"
    uni.mkdir()
    rng = np.random.default_rng(0)
    idx = pd.date_range("2022-01-03", periods=24 * 900, freq="h", tz="UTC")
    for sym, df in (("EURUSD", 6), ("XAUUSD", 3)):
        r = 0.0015 * rng.standard_t(df, idx.size) / np.sqrt(df / (df - 2))
        pd.DataFrame({"close": 1.1 * np.exp(np.cumsum(r))}, index=idx).to_parquet(
            uni / f"{sym}_H1.parquet")
    tape = tmp_path / "ticks" / "EURUSD"
    tape.mkdir(parents=True)
    for s in range(3):
        _tick_day(s).to_parquet(tape / f"2026-11-0{s + 2}.parquet")
    days = pd.date_range("2022-01-03", periods=900, freq="B", tz="UTC")
    panel = pd.DataFrame({f"S{i}_fam_x": 0.0008 + 0.01 * rng.standard_t(4, 900) / np.sqrt(2)
                          for i in range(6)}, index=[str(d.date()) for d in days])
    panel.iloc[:, 0] = np.where(rng.uniform(size=900) < 0.3, np.nan, panel.iloc[:, 0])
    pp = tmp_path / "daily_r.parquet"
    panel.to_parquet(pp)
    doc = lab.measure(universe=uni, tape=tmp_path / "ticks", panel_path=pp, budget_s=300)
    assert doc["status"] == "MEASURED"
    assert doc["symbols"]["EURUSD"]["noise"]["status"] == "MEASURED"
    assert doc["symbols"]["XAUUSD"]["noise"]["status"] == "UNMEASURED"
    assert doc["symbols"]["XAUUSD"]["daily"]["tail_alpha_loss"] is not None
    assert len(doc["sleeves"]) == 6
    pr = doc["proof"]
    assert pr["rebalances"] > 5
    for k in ("tail_tilt", "tail_scaled"):
        assert pr[k]["verdict"] in ("ADOPT", "REJECT", "INCONCLUSIVE")
        assert pr[k]["family_size"] == 2 and "loss_clip_days" in pr[k]
    c = lab.compact(doc)
    json.dumps(lab._clean(c), allow_nan=False)
    json.dumps(lab._clean(doc), allow_nan=False)


def test_lab_without_inputs_is_unmeasured_and_names_why(tmp_path: Path) -> None:
    import survival_inputs_lab as lab

    doc = lab.measure(universe=tmp_path, tape=tmp_path, panel_path=tmp_path / "x.parquet",
                      budget_s=10)
    assert doc["status"] == "UNMEASURED"
    assert "absent" in doc["panel_why"]
    assert doc["proof"]["tail_tilt"]["verdict"] == "UNMEASURED"
