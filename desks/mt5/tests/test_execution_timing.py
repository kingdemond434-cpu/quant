"""execution_timing: minute choice inside the placing hour, net of drift, UNMEASURED when thin."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from desks.mt5.research import execution_timing as et


def _world(tmp: Path, *, spread_at: dict[int, float], drift_per_min: float = 0.0,
           days: int = 40, family: str = "overnight_gap_decay", m1: bool = True,
           selector: str = "asia", params: dict[str, Any] | None = None,
           noise: float = 0.0) -> Path:
    bars = tmp / et.BARS_REL
    bars.mkdir(parents=True)
    reg = {"sleeves": {"S": {"status": "LIVE", "identity": {
        "symbol": "EURUSD", "family": family, "direction": "LONG", "selector": selector,
        "params": params or {}}}}}
    (tmp / et.REGISTRY_REL).parent.mkdir(parents=True, exist_ok=True)
    (tmp / et.REGISTRY_REL).write_text(json.dumps(reg))
    (tmp / et.UNIVERSE_REL).write_text(json.dumps({"EURUSD": {"tick_size": 0.0001}}))
    h1_idx = pd.date_range("2026-01-01", periods=24 * days, freq="h", tz="UTC")
    h1 = pd.DataFrame({"high": 1.0010, "low": 1.0, "close": 1.0005}, index=h1_idx)
    h1.to_parquet(bars / "EURUSD_H1.parquet")
    if m1:
        idx = pd.date_range("2026-01-01", periods=24 * 60 * days, freq="min", tz="UTC")
        spread = np.array([spread_at.get(m, 10) for m in idx.minute], dtype=float)
        if noise:
            spread = spread + np.random.default_rng(7).normal(0.0, noise, len(spread))
        opens = 1.0 + drift_per_min * idx.minute.to_numpy()
        pd.DataFrame({"open": opens, "spread": spread}, index=idx).to_parquet(
            bars / "EURUSD_M1.parquet")
    return tmp


def _row(root: Path) -> dict[str, Any]:
    row: dict[str, Any] = et.assess(root)["sleeves"][0]
    return row


def test_cheaper_minute_without_decay_is_recommended(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={20: 2}))
    assert row["entry"]["verdict"] == et.RECOMMEND
    assert row["entry"]["best_minute"] == 20
    assert row["entry"]["lift_R_per_trade"] > 0
    assert row["slippage"] == et.UNMEASURED


def test_cheaper_but_later_fill_that_gives_back_the_edge_is_refused(tmp_path: Path) -> None:
    # LONG; price rises steadily, so waiting to minute 20 forgoes far more than the spread saved.
    row = _row(_world(tmp_path, spread_at={20: 2}, drift_per_min=0.0001))
    assert row["entry"]["verdict"] == et.KEEP
    assert row["entry"]["edge_decay_R_at_cheapest"] > 0


def test_flat_surface_keeps_current(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={}))
    assert row["entry"]["verdict"] == et.KEEP
    assert row["entry"]["lift_R_per_trade"] == 0.0


def test_h1_only_symbol_is_unmeasured_not_cheap(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={}, m1=False))
    assert row["verdict"] == et.UNMEASURED
    assert "H1" in row["why"]


def test_thin_history_is_unmeasured(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={20: 2}, days=5))
    assert row["entry"]["verdict"] == et.UNMEASURED


def test_resting_stop_entry_is_not_selectable(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={20: 2}, family="session_range_breakout"))
    assert row["entry"]["verdict"] == et.NOT_SELECTABLE
    assert row["exit"]["verdict"] == et.UNMEASURED     # exit hour not declared


def test_exit_priced_only_in_its_declared_hour(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={20: 2}, family="session_range_breakout",
                      params={"exit_hour_utc": 19}))
    assert row["exit"]["verdict"] == et.RECOMMEND
    assert row["exit"]["n_trades"] == 40


def test_continuous_selector_entry_is_unmeasured_not_pooled(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={20: 2}, selector="continuous"))
    assert row["entry"]["verdict"] == et.UNMEASURED
    assert row["verdict"] == et.UNMEASURED


def test_noise_level_saving_is_not_recommended_after_selection(tmp_path: Path) -> None:
    # A 0.3-point true saving under 5-point per-bar noise: best-of-59 in-sample would pick it,
    # the Bonferroni lower bound must not.
    row = _row(_world(tmp_path, spread_at={20: 9.7}, noise=5.0))
    assert row["entry"]["verdict"] == et.KEEP
    lo, hi = row["entry"]["lift_ci_R"]
    assert lo <= row["entry"]["lift_R_per_trade"] <= hi


def test_no_intraday_reason_names_the_collector(tmp_path: Path) -> None:
    row = _row(_world(tmp_path, spread_at={}, m1=False))
    assert "INTRADAY_TIMEFRAMES" in row["why"]


def test_side_param_outranks_identity_direction() -> None:
    assert et.direction_sign({"direction": "LONG", "params": {"side": -1}}) == -1
    assert et.direction_sign({"direction": "SHORT"}) == -1
    assert et.direction_sign({}) == 0


def test_leg_is_wired_into_the_hourly_cycle() -> None:
    src = (Path(et.BASE) / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("execution_timing", execution_timing)' in src
    assert '"execution_timing": exm' in src
