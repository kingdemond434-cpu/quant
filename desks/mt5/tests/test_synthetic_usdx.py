"""`synthetic_usdx`: the ICE basket, exact on open/close, all six legs or nothing."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

import synthetic_usdx as su


def _write(root: Path, sym: str, idx: pd.DatetimeIndex, px: float) -> None:
    df = pd.DataFrame({"open": px, "high": px, "low": px, "close": px}, index=idx)
    df.to_parquet(root / f"{sym}_H1.parquet")


def test_the_basket_matches_the_ice_formula(tmp_path: Path) -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC")
    px = {"EURUSD": 1.10, "USDJPY": 150.0, "GBPUSD": 1.27, "USDCAD": 1.36,
          "USDSEK": 10.5, "USDCHF": 0.88}
    for s, p in px.items():
        _write(tmp_path, s, idx, p)
    out = su.build("H1", tmp_path)
    want = 50.14348112 * np.prod([px[s] ** w for s, w in su.WEIGHTS.items()])
    assert out is not None and np.allclose(out["close"], want) and len(out) == 5


def test_a_missing_leg_builds_nothing(tmp_path: Path) -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC")
    for s in list(su.WEIGHTS)[:-1]:
        _write(tmp_path, s, idx, 1.0)
    assert su.build("H1", tmp_path) is None


def test_bars_exist_only_where_every_leg_printed(tmp_path: Path) -> None:
    idx = pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC")
    for s in su.WEIGHTS:
        _write(tmp_path, s, idx if s != "USDSEK" else idx[1:4], 1.0)
    out = su.build("H1", tmp_path)
    assert list(out.index) == list(idx[1:4])
