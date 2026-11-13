"""The written replication rule for `spread_state` (2026-11-06: certificates held unreplicated
because the spec book had no rule and the lane's bars carried no spread).

FIDELITY: the lane's rebuild, written from the rule text, emits exactly the desk family's orders
(the test may import the implementation; the lane may not)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import replication_civilization as rc  # noqa: E402
from mt5desk.family_spread_state import family_spread_state  # noqa: E402


def _frame(n: int = 2400, seed: int = 3, volume: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    c = 1.1 + np.cumsum(rng.normal(0, 0.0015, n))
    df = pd.DataFrame({"open": c, "close": c + rng.normal(0, 0.0012, n)}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) + rng.uniform(0, 0.0015, n)
    df["low"] = df[["open", "close"]].min(axis=1) - rng.uniform(0, 0.0015, n)
    spread = rng.gamma(2.0, 6.0, n).round()
    spread[rng.choice(n, 25, replace=False)] = np.nan
    df["spread"] = spread
    if volume:
        df["tick_volume"] = rng.poisson(300, n).astype(float)
    return df


def _bars(df: pd.DataFrame) -> rc.Bars:
    cols = {k: df[k].to_numpy() for k in rc.VENUE_COLUMNS if k in df.columns}
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy(), cols=cols)


def _same(orig: list, ours: list) -> bool:
    return len(orig) == len(ours) and all(
        pd.Timestamp(o.time).value == q.t_ns and int(o.side) == q.side
        and abs(float(o.stop) - q.stop) < 1e-9 and abs(float(o.target) - q.target) < 1e-9
        and int(o.ttl_bars) == q.ttl_bars for o, q in zip(orig, ours, strict=True))


@pytest.mark.parametrize("volume", [True, False])
@pytest.mark.parametrize("params", [
    {"mode": "spike_reversion"},
    {"mode": "spike_reversion", "spike_pct": 0.9, "min_move_atr": 0.3, "hold_bars": 3},
    {"mode": "calm_continuation", "calm_pct": 0.3, "active_pct": 0.6, "min_move_atr": 0.2},
    {"mode": "calm_continuation", "norm_window": 120, "atr_n": 14, "stop_atr": 1.5, "rr": 2.0},
])
def test_rule_matches_the_registered_family(params: dict, volume: bool) -> None:
    df = _frame(volume=volume)
    orig = family_spread_state(df, **params)
    p, why = rc.resolve_spec("spread_state", {**params, "timeframe": "H1"}, "continuous", None,
                             symbol="TESTFX")
    assert p is not None, why
    ours = rc.SPEC_BOOK["spread_state"].build(_bars(df), p)
    assert len(orig) > 5 and _same(orig, ours)
    assert {int(o.side) for o in orig} == {1, -1}


def test_both_sides_survive_the_certificates_single_side_and_its_selector() -> None:
    df = _frame()
    p, _ = rc.resolve_spec("spread_state", {"mode": "spike_reversion"}, "asia", "LONG",
                           symbol="TESTFX")
    orders, _fills = rc.rebuild("spread_state", _bars(df), p, 0.0)
    assert {o.side for o in orders} == {1, -1}
    assert _same(family_spread_state(df, mode="spike_reversion"), orders)


def test_it_stands_aside_where_the_family_does() -> None:
    flat = _frame()
    flat["spread"] = 7.0
    cases = [(_frame(), {"mode": "widening_avoid"}), (_frame(n=600), {}), (flat, {}),
             (_frame().drop(columns="spread"), {})]
    for df, params in cases:
        assert family_spread_state(df, **params) == []
        p, _ = rc.resolve_spec("spread_state", params, None, None, symbol="X")
        assert rc.SPEC_BOOK["spread_state"].build(_bars(df), p) == []


def test_load_bars_carries_the_venue_columns(tmp_path: Path) -> None:
    df = _frame(n=400)
    df.index.name = "time"
    df.to_parquet(tmp_path / "TESTFX_H1.parquet")
    b = rc.load_bars("TESTFX", "H1", universe=tmp_path)
    assert b is not None and set(b.cols) == {"spread", "tick_volume"}
    np.testing.assert_array_equal(b.cols["spread"], df["spread"].to_numpy())
