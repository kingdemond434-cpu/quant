"""The written replication rule for `jump` (2026-11-06: certificates held unreplicated because
the spec book had no rule).

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
from mt5desk.families_orthogonal import family_jump  # noqa: E402


def _frame(n: int = 2000, seed: int = 9) -> pd.DataFrame:
    """A diffusion with fat-tailed shocks, so both jump directions occur."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    r = rng.normal(0, 1e-3, n)
    shocks = rng.choice(n, 40, replace=False)
    r[shocks] += rng.choice([-1, 1], 40) * rng.uniform(6e-3, 1.2e-2, 40)
    c = 1.1 * np.exp(np.cumsum(r))
    df = pd.DataFrame({"open": np.concatenate([[c[0]], c[:-1]]), "close": c}, index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) * (1 + rng.uniform(0, 5e-4, n))
    df["low"] = df[["open", "close"]].min(axis=1) * (1 - rng.uniform(0, 5e-4, n))
    return df


def _bars(df: pd.DataFrame) -> rc.Bars:
    return rc.bars_from_arrays(df.index.as_unit("ns").asi8, df["open"].to_numpy(),
                               df["high"].to_numpy(), df["low"].to_numpy(),
                               df["close"].to_numpy())


def _same(orig: list, ours: list) -> bool:
    return len(orig) == len(ours) and all(
        pd.Timestamp(o.time).value == q.t_ns and int(o.side) == q.side
        and abs(float(o.stop) - q.stop) < 1e-9 and abs(float(o.target) - q.target) < 1e-9
        and int(o.ttl_bars) == q.ttl_bars for o, q in zip(orig, ours, strict=True))


@pytest.mark.parametrize("params", [
    {}, {"mode": "revert"}, {"lookback": 24, "jump_k": 3.0, "cooldown_bars": 2},
    {"lookback": 96, "atr_n": 14, "stop_atr": 2.0, "rr": 2.0, "ttl_bars": 24},
])
def test_rule_matches_the_registered_family(params: dict) -> None:
    df = _frame()
    orig = family_jump(df, **params)
    p, why = rc.resolve_spec("jump", {**params, "timeframe": "H1"}, "continuous", None,
                             symbol="TESTFX")
    assert p is not None, why
    ours = rc.SPEC_BOOK["jump"].build(_bars(df), p)
    assert len(orig) > 5 and _same(orig, ours)
    assert {int(o.side) for o in orig} == {1, -1}


def test_both_sides_survive_the_certificates_single_side_and_its_selector() -> None:
    df = _frame()
    p, _ = rc.resolve_spec("jump", {"mode": "revert"}, "asia", "SHORT", symbol="TESTFX")
    orders, _fills = rc.rebuild("jump", _bars(df), p, 0.0)
    assert {o.side for o in orders} == {1, -1}
    assert _same(family_jump(df, mode="revert"), orders)


def test_it_stands_aside_where_the_family_does() -> None:
    for df, params in ((_frame(), {"mode": "drift"}), (_frame(), {"lookback": 3}),
                       (_frame(n=60), {})):
        assert family_jump(df, **params) == []
        p, _ = rc.resolve_spec("jump", params, None, None, symbol="X")
        assert rc.SPEC_BOOK["jump"].build(_bars(df), p) == []
