"""The model-disagreement factory (ROMAN-0388..0403, 0578, 0797..0812): features compute on a
simulated Heston world, every row is point-in-time, and the contract machinery returns GAIN on
planted effects and NO_GAIN / UNMEASURED on noise."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import model_disagreement as md  # noqa: E402

from libs.research import sensor_engines as se  # noqa: E402
from libs.research.sensor_contract import defects  # noqa: E402


def _world(days: int = 200, bars: int = 12, seed: int = 3) -> tuple[pd.DataFrame, dict]:
    """Heston truth at H1-ish resolution; the 'market IV' is sqrt(v) plus a premium and noise."""
    rng = np.random.default_rng(seed)
    n, dt = days * bars, 1.0 / 252.0 / bars
    kappa, theta, sig, rho = 3.0, 0.04, 0.8, -0.7
    v = np.empty(n)
    lp = np.empty(n + 1)
    lp[0], vp = math.log(100.0), 0.04
    z1 = rng.standard_normal(n)
    z2 = rho * z1 + math.sqrt(1 - rho * rho) * rng.standard_normal(n)
    for i in range(n):
        lp[i + 1] = lp[i] - 0.5 * vp * dt + math.sqrt(vp * dt) * z2[i]
        vp = max(vp + kappa * (theta - vp) * dt + sig * math.sqrt(vp * dt) * z1[i], 0.0)
        v[i] = vp
    px = np.exp(lp)
    idx = pd.date_range("2023-01-02", periods=days, freq="D", tz="UTC").repeat(bars) \
        + pd.to_timedelta(np.tile(np.arange(bars), days), unit="h")
    bars_df = pd.DataFrame({"open": px[:-1], "close": px[1:],
                            "high": np.maximum(px[:-1], px[1:]) * 1.0004,
                            "low": np.minimum(px[:-1], px[1:]) * 0.9996,
                            "tick_volume": rng.integers(100, 1000, n)}, index=idx)
    dayv = v.reshape(days, bars).mean(axis=1)
    dates = sorted(set(idx.date))
    iv = {d: math.sqrt(max(x, 1e-4)) + 0.02 + 0.004 * rng.standard_normal()
          for d, x in zip(dates, dayv, strict=True)}
    return bars_df, iv


@pytest.fixture(scope="module")
def world() -> tuple[md.Daily, list[dict]]:
    bars, iv = _world()
    d = md.build_daily(md.daily_from_h1(bars), iv)
    rows, complete = md.build_rows(d, start=170, heavy_every=10)
    assert complete
    md.attach_entropy(rows, d)
    return d, rows


def test_features_compute_on_a_heston_world(world: tuple[md.Daily, list[dict]]) -> None:
    d, rows = world
    assert len(rows) == len(d) - 170
    last = rows[-1]
    for f in md.FEATURES:
        if f == "model_ensemble_entropy":
            continue
        assert math.isfinite(last[f]), f
    assert 0.0 <= last["model_ensemble_entropy"] <= 1.0
    assert last["vol_disagreement"] > 0 and last["valuation_disagreement"] > 0
    assert all(math.isfinite(last[f"rough_z{k}"]) for k in range(md.N_ROUGH))
    assert all(f"vf30_{m}" in last for m in md.MODEL_NAMES)
    day = date.fromisoformat(last["event_time"][:10])
    assert datetime.fromisoformat(last["available_time"]) == md.available_at(day)


def test_rows_are_point_in_time(world: tuple[md.Daily, list[dict]]) -> None:
    """Truncating every input after day i must leave day i's row unchanged."""
    d, rows = world
    i = 182
    cut, _ = md.build_rows(d.head(i + 1), start=170, heavy_every=10)
    full = next(r for r in rows if r["day_index"] == i)
    for k, v in cut[-1].items():
        if k == "model_ensemble_entropy":
            continue
        assert v == full[k] or (isinstance(v, float) and math.isnan(v) and math.isnan(full[k])), k
    # a day whose knowable instant is after `now` is never computed
    now = md.available_at(d.dates[175]) - timedelta(minutes=1)
    early, _ = md.build_rows(d, start=170, heavy_every=10, now=now)
    assert [r["day_index"] for r in early] == list(range(170, 175))


def test_contracts_return_verdicts_and_name_their_rows(world: tuple[md.Daily, list[dict]]
                                                       ) -> None:
    d, rows = world
    got = md.measure_contracts(md.frame_for_contracts(rows, d), "SYN")
    romans = {c["roman"] for c in got}
    assert romans == {"ROMAN-0400", "ROMAN-0401", "ROMAN-0402", "ROMAN-0403"}
    for c in got:
        assert c["verdict"] in (se.GAIN, se.NO_GAIN, se.UNMEASURED)
        assert c["roman"] in c["cards"] and "ROMAN-0578" in c["cards"]
    # 30 rows is far below every min_n: never a pass
    assert all(c["verdict"] == se.UNMEASURED for c in got)


def _planted(n: int = 1100, seed: int = 5, plant: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    def ar(phi: float, sd: float) -> np.ndarray:
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + sd * rng.standard_normal()
        return x
    vd_persistent = ar(0.98, 0.2)
    iv = 0.18 * np.exp(ar(0.98, 0.05))
    val = ar(0.97, 0.25)
    vd = 0.3 + 0.1 * vd_persistent
    sigma = iv / math.sqrt(252) * (np.exp(1.5 * vd_persistent) if plant else 1.0)
    ret = np.zeros(n)
    val_hi = md._expanding_flag(val)
    vd_hi = md._expanding_flag(vd)
    for t in range(1, n):
        mu = 0.0
        if plant:
            mu += 0.6 * sigma[t] * val_hi[t - 1]
            mu += -0.6 * np.sign(ret[t - 1]) * sigma[t] * vd_hi[t - 1]
        ret[t] = mu + sigma[t] * rng.standard_normal()
    shock = rng.normal(0, 1, n)
    vd_iid = 0.3 + 0.1 * shock
    rng_lvl = np.convolve(np.r_[np.zeros(5), shock], np.ones(5) / 5, mode="valid")[:n]
    log_range = 0.01 * np.exp((0.8 if plant else 0.0) * np.r_[0.0, rng_lvl[:-1]]
                              + 0.1 * rng.standard_normal(n))
    return pd.DataFrame({"market_iv": iv, "vol_disagreement": vd,
                         "tail_disagreement": 0.05 + 0.01 * rng.standard_normal(n),
                         "valuation_disagreement": val, "ret": ret,
                         "log_range": log_range, "tick_volume": np.full(n, np.nan),
                         "_vd_iid": vd_iid})


def test_contract_machinery_finds_planted_effects_and_not_noise() -> None:
    f = _planted()
    got = {c["roman"]: c for c in md.measure_contracts(f, "PLANT")}
    assert got["ROMAN-0400"]["verdict"] == se.GAIN
    assert got["ROMAN-0401"]["verdict"] == se.GAIN
    assert got["ROMAN-0403"]["verdict"] == se.GAIN
    # the range effect is planted on an iid disagreement series (order, not level)
    g = f.assign(vol_disagreement=f["_vd_iid"])
    rank = next(c for c in md.measure_contracts(g, "PLANT") if c["roman"] == "ROMAN-0402")
    assert rank["verdict"] == se.GAIN
    noise = _planted(plant=False, seed=8)
    for c in md.measure_contracts(noise, "NOISE"):
        assert c["verdict"] in (se.NO_GAIN, se.UNMEASURED), c["roman"]


def test_sensor_rows_are_admitted_and_dry_run_end_to_end(tmp_path: Path,
                                                         world: tuple[md.Daily, list[dict]]
                                                         ) -> None:
    d, rows = world
    now = md.available_at(d.dates[-1]) + timedelta(hours=2)
    obs = md.sensor_rows(rows, "XAUUSD", "ws_model_disagreement_XAUUSD", now)
    assert len(obs) >= 9 and all(defects(o) == [] for o in obs)
    assert {o.knowable_basis for o in obs} == {"declared_lag"}
    # end to end, dry run, on fixtures (the container has no vol reference history)
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps({"XAUUSD": {"symbol": "XAUUSD"}}), "utf-8")
    bars, iv = _world(days=200, bars=8, seed=9)
    bars.to_parquet(uni / "XAUUSD_H1.parquet")
    ref = tmp_path / "vol" / "reference"
    ref.mkdir(parents=True)
    (ref / "^GVZ.json").write_text(json.dumps(
        {"fetched_at": "x", "series": {k.isoformat(): v * 100 for k, v in iv.items()}}), "utf-8")
    rep = md.run(now=datetime(2024, 1, 1, tzinfo=UTC), budget_s=60, heavy_every=10, days=12,
                 dry_run=True, universe_dir=uni, vol_dir=tmp_path / "vol", lake=tmp_path)
    sym = rep["symbols"][0]
    assert sym["symbol"] == "XAUUSD" and sym["status"] == "COMPUTED" and sym["rows"] == 12
    assert not list(tmp_path.glob("ws_*.csv"))          # dry run wrote nothing
    empty = md.run(now=datetime(2024, 1, 1, tzinfo=UTC), dry_run=True, universe_dir=uni,
                   vol_dir=tmp_path / "nothing", lake=tmp_path)
    assert empty["symbols"][0]["status"] == md.UNMEASURED
