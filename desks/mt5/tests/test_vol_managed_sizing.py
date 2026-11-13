"""Vol-managed sizing: the Rule-1 proof a GARCH forecast needs before it sizes (2026-11-13).

Pinned: the weight is causal (built from forecasts before t), two-sided and clipped; a sleeve
whose symbol cannot be read is UNMEASURED; a book where scaling helps is marked EARNS only when it
also beats the leverage-matched book; no matrix is UNMEASURED, never a verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

import vol_managed_sizing as V  # noqa: E402


def test_weights_are_causal_two_sided_and_clipped() -> None:
    idx = pd.date_range("2020-01-01", periods=600, freq="D", tz="UTC")
    var = pd.Series(1.0, index=idx)
    var.iloc[400] = 100.0
    var.iloc[450] = 1e-4
    w = V.weights(var)
    assert w.iloc[399] == pytest.approx(1.0)
    assert w.iloc[400] == V.W_MIN and w.iloc[450] == V.W_MAX
    var2 = var.copy()
    var2.iloc[500:] = 50.0
    assert V.weights(var2).iloc[:500].equals(w.iloc[:500])     # the future never moves the past


def test_symbol_is_read_from_the_sleeve_name_or_unmeasured() -> None:
    have = {"XAUUSD", "EURUSD", "USDJPY"}
    assert V.symbol_of("gold_asia", have) == "XAUUSD"
    assert V.symbol_of("EURUSD_london_trend", have) == "EURUSD"
    assert V.symbol_of("mystery_sleeve", have) is None


def _book(scaling_helps: bool, n: int = 900) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(3)
    idx = pd.date_range("2020-01-01", periods=n, freq="D", tz="UTC")
    var = pd.Series(np.where((np.arange(n) // 60) % 2 == 0, 1.0, 9.0), index=idx)
    base = rng.normal(0.15, 1.0, n)
    # helps: the storm days carry the losses, so cutting them in storms raises growth
    r = np.where(var.to_numpy() > 1, base - (0.6 if scaling_helps else -0.6), base)
    daily = pd.DataFrame({"EURUSD_x": r}, index=idx)
    fc = {"EURUSD": {"ewma": var, "garch": var}}
    return daily, fc


def test_earns_only_against_both_baselines() -> None:
    daily, fc = _book(True)
    out = V.evaluate(daily, {"EURUSD_x": "EURUSD"}, fc, fraction=0.05, reps=200)
    assert out["verdict"]["garch"]["delta_vs_none_yr"] > 0
    assert out["verdict"]["garch"]["EARNS"] is True
    daily, fc = _book(False)
    out = V.evaluate(daily, {"EURUSD_x": "EURUSD"}, fc, fraction=0.05, reps=200)
    assert out["verdict"]["garch"]["EARNS"] is False


def test_unmapped_sleeves_and_absent_matrix_are_unmeasured(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    daily, fc = _book(True)
    out = V.evaluate(daily, {}, fc, reps=50)
    assert out["sleeves"]["EURUSD_x"]["status"] == "UNMEASURED"
    assert out["verdict"]["garch"] == "UNMEASURED"
    monkeypatch.setattr(V, "MATRIX", tmp_path / "absent.parquet")
    monkeypatch.setattr(V, "REPORT", tmp_path / "VOL_MANAGED_SIZING.json")
    assert V.run(reps=10)["status"] == "UNMEASURED"
