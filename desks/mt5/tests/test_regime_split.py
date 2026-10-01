"""The regime split: a family gated by its instrument's control-room regime, and the purged
walk-forward that kills a regime cell whose edge lives in one stretch of history.

Pinned: the gate reads only the label of a day BEFORE the signal (a future bar cannot change
which signals pass), an empty axis means "any", an unknown base family yields nothing, and the
walk-forward fails a cell when any measured fold loses or too few folds are measured.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families_orthogonal as fo  # noqa: E402

from research import regime_split_miner as rsm  # noqa: E402


def _bars(days: int = 700, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=days * 24, freq="h", tz="UTC")
    vol = np.repeat(np.where(np.arange(days) // 60 % 2, 0.002, 0.0006), 24)
    c = np.exp(np.cumsum(rng.normal(scale=vol))) * 100
    o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.0004,
                         "low": np.minimum(o, c) * 0.9996, "close": c,
                         "spread": np.full(idx.size, 2.0), "tick_volume": np.full(idx.size, 100)},
                        index=idx)


def test_registered_and_price_only() -> None:
    assert fo.ORTHOGONAL_FAMILIES["regime_split"] is fo.family_regime_split
    assert fo.FAMILY_INPUTS["regime_split"][0].startswith("price only")


def test_gate_is_a_subset_and_axes_partition() -> None:
    d = _bars()
    base = fo.ORTHOGONAL_FAMILIES["drawdown_conditional"](d)
    every = fo.family_regime_split(d, base_family="drawdown_conditional")
    parts = [fo.family_regime_split(d, base_family="drawdown_conditional", vol=v)
             for v in rsm.VOLS]
    t_base = {s.time for s in base}
    assert {s.time for s in every} <= t_base
    assert sum(len(p) for p in parts) == len(every)
    assert all({s.time for s in p} <= t_base for p in parts)


def test_future_bars_cannot_change_past_gating() -> None:
    d = _bars()
    cut = d.index[len(d) * 2 // 3]
    full = fo.family_regime_split(d, base_family="drawdown_conditional", vol="high")
    short = fo.family_regime_split(d[d.index < cut], base_family="drawdown_conditional",
                                   vol="high")
    early = {s.time for s in full if s.time < cut - pd.Timedelta(days=2)}
    assert early <= {s.time for s in short}


def test_unknown_or_self_base_yields_nothing() -> None:
    d = _bars(400)
    assert fo.family_regime_split(d, base_family="no_such_family") == []
    assert fo.family_regime_split(d, base_family="regime_split") == []


def test_walk_forward_kills_a_losing_fold_and_keeps_a_steady_edge() -> None:
    n = 10_000
    pos = list(range(100, n - 100, 100))
    steady = rsm.purged_walk_forward([0.002] * len(pos), pos, n, cost=0.001)
    assert steady["passed"] and steady["measured"] == rsm.FOLDS
    pnl = [0.002 if p < n * 0.8 else -0.004 for p in pos]
    assert not rsm.purged_walk_forward(pnl, pos, n, cost=0.001)["passed"]
    sparse = rsm.purged_walk_forward([0.01] * 6, [100, 200, 300, 400, 500, 600], n, cost=0.0)
    assert not sparse["passed"]


def test_walk_forward_purges_trades_at_fold_boundaries() -> None:
    n = 1000
    wf = rsm.purged_walk_forward([1.0], [200], n, cost=0.0, folds=5, embargo=24)
    assert sum(f["n"] for f in wf["folds"]) == 0


def test_union_is_charged_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import json
    monkeypatch.setattr(rsm, "CHARGED", tmp_path / "charged.json")
    monkeypatch.setattr(rsm, "TRIALS", tmp_path / "trials.jsonl")
    rows = [{"cell": "A.regime_split.x.low_trend"}, {"cell": "B.regime_split.x.low_trend"}]
    assert rsm.charge(rows) == (2, 2)
    assert rsm.charge([*rows, {"cell": "C.regime_split.x.low_trend"}]) == (1, 3)
    assert rsm.charge(rows) == (0, 3)
    lines = (tmp_path / "trials.jsonl").read_text().splitlines()
    assert [json.loads(x)["cells_screened"] for x in lines] == [2, 1]


def test_lane_never_admits_single_name_equities() -> None:
    from research.universe_policy import may_hypothesise
    assert all(may_hypothesise(s, rsm.FAMILY) for s in rsm.lane())
