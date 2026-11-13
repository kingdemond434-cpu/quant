"""GARCH vs EWMA per instrument (2026-11-13, principal: "yes use garch").

Pinned: the pre-stated choice rule (GARCH default, GJR on the selection half, blend then EWMA only
when the GARCH variant fails to fit or scores worse); evidence is the HOLDOUT half; days are UTC
dates with enough bars; a GARCH-generated series is recognised as GARCH and beats EWMA on the
holdout; the leg writes both artifacts; the daily cycle runs it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import garch_vs_ewma as V  # noqa: E402


def _garch_series(n: int, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    omega, alpha, beta = 2e-6, 0.10, 0.85
    h = omega / (1 - alpha - beta)
    r = np.empty(n)
    for i in range(n):
        r[i] = np.sqrt(h) * rng.standard_normal()
        h = omega + alpha * r[i] ** 2 + beta * h
    return r


def _h1_from_daily(r: np.ndarray) -> pd.DataFrame:
    days = pd.bdate_range("2018-01-02", periods=len(r) + 1, tz="UTC")
    close = 1.1 * np.exp(np.concatenate([[0.0], np.cumsum(r)]))
    idx, px = [], []
    for d, c in zip(days, close, strict=True):
        for h in range(24):
            idx.append(d + pd.Timedelta(hours=h))
            px.append(c)
    return pd.DataFrame({"close": px}, index=pd.DatetimeIndex(idx))


def test_the_rule_defaults_to_garch_and_falls_back_only_on_worse_or_no_fit() -> None:
    q = {"ewma": 1.0, "garch": 0.9, "gjr": 0.95, "blend": 0.92}
    assert V.choose(q, True)[0] == "garch"
    assert V.choose({**q, "gjr": 0.8}, True)[0] == "gjr"
    assert V.choose({**q, "garch": 1.1, "gjr": 1.2, "blend": 0.99}, True)[0] == "blend"
    assert V.choose({**q, "garch": 1.1, "gjr": 1.2, "blend": 1.05}, True)[0] == "ewma"
    assert V.choose(q, False)[0] == "ewma"


def test_days_are_utc_dates_with_enough_bars() -> None:
    df = _h1_from_daily(np.array([0.01, -0.02]))
    stub = pd.DataFrame({"close": [9.9]}, index=pd.DatetimeIndex(
        [df.index[-1] + pd.Timedelta(days=3)]))
    r = V.daily_returns(pd.concat([df, stub]))
    assert r == pytest.approx([0.01, -0.02])


def test_a_garch_series_is_read_as_garch_and_wins_the_holdout() -> None:
    r = _garch_series(1100)
    m = V.measure("X", r)
    assert m["status"] == "MEASURED" and m["chosen"] in ("garch", "gjr", "blend")
    assert m["dm_holdout_garch"]["mean_diff"] > 0
    assert m["n_oos"] == len(r) - V.MIN_TRAIN


def test_too_short_is_unmeasured() -> None:
    assert V.measure("X", _garch_series(300))["status"] == "UNMEASURED"


def test_the_leg_writes_the_report_and_the_choice_file(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    uni = tmp_path / "universe"
    uni.mkdir()
    _h1_from_daily(_garch_series(1000)).to_parquet(uni / "EURUSD_H1.parquet")
    monkeypatch.setattr(V.pc, "UNI", uni)
    monkeypatch.setattr(V, "REPORT", tmp_path / "GARCH_VS_EWMA.json")
    monkeypatch.setattr(V, "CHOICE", tmp_path / "VOL_FORECASTER.json")
    rep = V.run(["EURUSD"], budget_s=600)
    assert rep["symbols_tested"] == 1
    got = json.loads((tmp_path / "VOL_FORECASTER.json").read_text("utf-8"))["symbols"]["EURUSD"]
    assert got["model"] in V.MODELS and got["next_var"] > 0 and got["ewma_next_var"] > 0
    assert json.loads((tmp_path / "GARCH_VS_EWMA.json").read_text("utf-8"))["pooled"][
        "symbols_measured"] == 1


def test_the_daily_cycle_runs_it() -> None:
    src = (_DESK / "research" / "daily_cycle.py").read_text("utf-8")
    assert '("vol_forecast", _vol_forecast)' in src and "import garch_vs_ewma" in src
