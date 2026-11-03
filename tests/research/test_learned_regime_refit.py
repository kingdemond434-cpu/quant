"""Regime-triggered refits for the learned miners (2026-10-20, GAP_MAP row 29).

The CN shops refit when the regime moves, not on a calendar. A break is a change of the panel's
volatility state against its own trailing year, read from rows <= t; the model is refitted the
row after and trains from the break onward. These tests pin the four things that make that
honest: the break is causal, a planted regime change is found, the clock schedule is unchanged
when no break is asked for, and the future never changes a past prediction.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.models import learned_propagation as LP  # noqa: E402

WF = {"min_train": 300, "refit_every": 50, "window": 600}


def _panel(ret: np.ndarray) -> LP.Panel:
    dates = pd.bdate_range("2019-01-01", periods=ret.shape[0], tz="UTC")
    return LP.Panel(dates, [f"S{j:02d}" for j in range(ret.shape[1])], ret,
                    np.full(ret.shape, 5e-5))


def _vol_shift(t_n: int = 1200, at: int = 700, seed: int = 4) -> np.ndarray:
    """Quiet panel that turns four times as volatile at row `at`."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0, 0.005, (t_n, 8))
    r[at:] *= 4.0
    return r


def test_a_planted_regime_change_is_found_where_it_happened() -> None:
    br = LP.regime_breaks(LP.design(_panel(_vol_shift())))
    assert br and any(700 <= b <= 760 for b in br), br


def test_a_break_is_read_from_the_past_only() -> None:
    ret = _vol_shift()
    full = LP.regime_breaks(LP.design(_panel(ret)))
    for cut in (650, 720, 900):
        part = LP.regime_breaks(LP.design(_panel(ret[:cut])))
        assert part == tuple(b for b in full if b < cut), cut


def test_the_clock_schedule_is_unchanged_without_breaks() -> None:
    assert LP.refit_points(1000, 300, 50) == list(range(300, 1000, 50))
    seen: list[tuple[int, int]] = []

    def fit(lo: int, k: int, _prev: Any) -> int:
        seen.append((lo, k))
        return 1

    LP.walk_forward(1000, 2, fit, lambda m, a, b: np.zeros((b - a, 2)), **WF)
    assert seen == [(max(0, k - 600), k) for k in range(300, 1000, 50)]


def test_a_break_adds_a_refit_and_trains_on_the_new_regime() -> None:
    seen: list[tuple[int, int]] = []

    def fit(lo: int, k: int, _prev: Any) -> int:
        seen.append((lo, k))
        return 1

    preds = LP.walk_forward(1000, 2, fit, lambda m, a, b: np.full((b - a, 2), float(a)),
                            breaks=(420,), **WF)
    ks = [k for _lo, k in seen]
    assert 421 in ks and set(range(300, 1000, 50)) <= set(ks)
    for lo, k in seen:
        if k > 420:
            assert lo == max(k - 600, min(420, k - LP.POST_BREAK_MIN))
    assert preds[421, 0] == 421.0 and preds[420, 0] == 400.0     # the break's refit takes over


def test_perturbing_the_future_never_changes_a_past_regime_prediction() -> None:
    ret = _vol_shift(t_n=900, at=500)
    t0 = 640
    fut = ret.copy()
    fut[t0 + 1:] = np.random.default_rng(99).normal(0, 0.05, fut[t0 + 1:].shape)
    cfg = LP.GNN_GRID[-1]
    assert cfg.get("refit") == "regime"
    p1 = LP.predictions(LP.design(_panel(ret)), "gnn", cfg, **WF)
    p2 = LP.predictions(LP.design(_panel(fut)), "gnn", cfg, **WF)
    assert np.isfinite(p1[WF["min_train"]:t0 + 1]).any()
    np.testing.assert_allclose(p1[:t0 + 1], p2[:t0 + 1], equal_nan=True)


def test_every_model_charges_one_regime_configuration_and_refuses_unknown_modes() -> None:
    import learned_miners as LM
    from mt5desk import families_orthogonal as FO
    for spec in LM.MINERS.values():
        grid = spec["grid"]
        assert grid[0].get("refit", "clock") == "clock"           # the primary is unchanged
        regime = [c for c in grid if c.get("refit") == "regime"]
        assert len(regime) == 1
        assert {k: v for k, v in regime[0].items() if k != "refit"} == grid[0]
        fn = FO.ORTHOGONAL_FAMILIES[spec["family"]]
        frame = pd.DataFrame({"close": [1.0]})
        assert fn(frame, symbol="EURUSD", peer_symbols=["GBPUSD"], refit="weekly") == []
