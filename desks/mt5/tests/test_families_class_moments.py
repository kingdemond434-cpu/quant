"""The three commodity class books: registered, ranked on the class, causal, commodity-only."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_class_moments as cm  # noqa: E402
from mt5desk import families_cross_sectional as xs  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from research import axis_registry as ax  # noqa: E402
from research import elitequant_breadth as eb  # noqa: E402
from research import universe_policy as up  # noqa: E402

DAYS = 900


def _panel(skews: list[float], seed: int = 7) -> tuple[pd.DataFrame, np.ndarray]:
    """Member 0 is the cell's own leg. Each member's daily returns carry a known skew: a
    lognormal shock signed by `s`, so +s is lottery-like and -s crash-like."""
    rng = np.random.default_rng(seed)
    cols = []
    for s in skews:
        base = rng.normal(0, 0.01, DAYS)
        if s:
            jump = (rng.lognormal(0, 1, DAYS) - np.exp(0.5)) * 0.004 * np.sign(s)
            base = base + jump
        cols.append(base)
    logv = np.cumsum(np.column_stack(cols), axis=0)
    idx = pd.date_range("2020-01-01 22:00", periods=DAYS, freq="D", tz="UTC")
    close = np.exp(logv[:, 0])
    o = np.r_[close[0], close[:-1]]
    d = pd.DataFrame({"open": o, "high": np.maximum(o, close) * 1.001,
                      "low": np.minimum(o, close) * 0.999, "close": close}, index=idx)
    return d, logv


@pytest.fixture
def patch_panel(monkeypatch):
    def install(d: pd.DataFrame, logv: np.ndarray) -> None:
        def fake(frame, symbol, *, decision_hour=22, max_stale_h=12.0):
            n = len(frame)
            return {"klass": "commodity", "members": [symbol] + [f"P{i}" for i in
                                                                  range(logv.shape[1] - 1)],
                    "own": 0, "pos": np.arange(n), "logv": logv[:n], "orient": 1,
                    "close": frame["close"].to_numpy(dtype=float)}
        monkeypatch.setattr(xs, "class_panel", fake)
    return install


def test_registered_seeded_on_commodity_legs_and_mapped():
    for name, fn in cm.CLASS_MOMENT_FAMILIES.items():
        assert fo.ORTHOGONAL_FAMILIES[name] is fn
        assert fo.FAMILY_INPUTS[name] == fo.FAMILY_INPUTS["cross_sectional_class_momentum"]
        assert eb.FAMILIES[name] is fn and name in eb.SYMBOL_KEYED
        assert eb.CLASS_ONLY[name] == {"commodity"}
        assert eb.SOURCE_ID[name] == "github:paperswithbacktest/awesome-systematic-trading"
        assert ax.FAMILY_TABLE[name][1] == "cross_asset"
        # a claim about commodity classes: share CFDs never reach it
        assert name not in up.CROSS_SECTIONAL_FAMILIES


def test_skew_book_buys_the_crash_skewed_leg_and_sells_the_lottery(patch_panel):
    d, logv = _panel([-1, 0, 0, 0, 0, 1, 1])
    patch_panel(d, logv)
    sides = {s.side for s in cm.family_cross_sectional_class_skew(d, symbol="X", hold_d=5)}
    assert sides == {1}
    d, logv = _panel([1, 0, 0, 0, 0, -1, -1])
    patch_panel(d, logv)
    sides = {s.side for s in cm.family_cross_sectional_class_skew(d, symbol="X", hold_d=5)}
    assert sides == {-1}


def test_asymmetry_book_sells_the_up_tail_leg(patch_panel):
    d, logv = _panel([1, 0, 0, 0, 0, -1, -1])
    patch_panel(d, logv)
    sigs = cm.family_cross_sectional_class_asymmetry(d, symbol="X", hold_d=5)
    assert sigs and sum(s.side for s in sigs) < 0


@pytest.mark.parametrize("name", sorted(cm.CLASS_MOMENT_FAMILIES))
def test_causal(name, patch_panel):
    d, logv = _panel([1, -1, 0, 0.5, -0.5, 0, 1])
    patch_panel(d, logv)
    fn = cm.CLASS_MOMENT_FAMILIES[name]
    full = fn(d, symbol="X", hold_d=5)
    cut = d.index[700]
    part = {(s.time, s.side) for s in fn(d.iloc[:720], symbol="X", hold_d=5) if s.time < cut}
    assert part == {(s.time, s.side) for s in full if s.time < cut}


def test_no_class_no_signals():
    d, _ = _panel([0, 0, 0, 0, 0])
    for fn in cm.CLASS_MOMENT_FAMILIES.values():
        assert fn(d, symbol="") == []
