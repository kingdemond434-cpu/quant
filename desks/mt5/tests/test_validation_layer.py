"""Calibration scores, the second replay, the red team, capacity, the hypothesis graph, manifest.

The load-bearing properties: proper scores reward the true distribution and nothing else; the
second replay is written from the contract and agrees with the engine on real bars; a placebo
keeps the real trade's risk geometry; capacity never raises a bound; the graph remembers what it
buried; the manifest chain detects an edit.
"""

from __future__ import annotations

import json
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

from libs.research.hypothesis_graph import (  # noqa: E402
    BORN,
    FAILED,
    Graph,
    Node,
    record_verdicts,
    region_key,
)
from libs.risk.capacity import bound_from_capacity, capacity  # noqa: E402
from libs.validation import calibration as cal  # noqa: E402
from libs.validation import redteam, replay2  # noqa: E402
from research import live_manifest  # noqa: E402

# ------------------------------------------------------------------------------------------
# Calibration
# ------------------------------------------------------------------------------------------

def test_proper_scores_are_minimised_by_the_true_distribution():
    rng = np.random.default_rng(0)
    y = rng.normal(0.0, 1.0, size=20000)
    true = cal.scorecard(y, np.zeros_like(y), np.ones_like(y))
    over = cal.scorecard(y, np.zeros_like(y), np.full_like(y, 0.5))     # overconfident
    wide = cal.scorecard(y, np.zeros_like(y), np.full_like(y, 2.0))     # too wide
    biased = cal.scorecard(y, np.full_like(y, 0.5), np.ones_like(y))
    for other in (over, wide, biased):
        assert true.crps < other.crps
        assert true.log_score < other.log_score
    assert true.pit_ks < 0.02 and over.pit_ks > 0.1
    assert abs(true.sharpness_ratio - 1.0) < 0.05 and over.sharpness_ratio > 1.5


def test_paired_improvement_finds_the_better_forecast():
    rng = np.random.default_rng(1)
    y = rng.normal(0.0, 1.0, size=5000)
    out = cal.paired_improvement(y, np.full_like(y, 0.8), np.ones_like(y),
                                 np.zeros_like(y), np.ones_like(y))
    assert out["crps_gain"] > 0 and out["t"] > 5


def test_crps_closed_form_matches_a_monte_carlo_estimate():
    rng = np.random.default_rng(2)
    y, mu, s = 0.7, 0.2, 1.3
    x = rng.normal(mu, s, size=200000)
    mc = np.mean(np.abs(x - y)) - 0.5 * np.mean(np.abs(x[:100000] - x[100000:]))
    assert cal.crps_gaussian([y], [mu], [s])[0] == pytest.approx(mc, abs=0.01)


# ------------------------------------------------------------------------------------------
# Replay and red team
# ------------------------------------------------------------------------------------------

def _bars(days: int = 300, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h", tz="UTC")
    c = np.exp(np.cumsum(rng.normal(scale=0.001, size=idx.size))) * 1800
    o = np.concatenate([[c[0]], c[:-1]])
    spread = np.abs(rng.normal(scale=0.002, size=idx.size)) * c
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + spread,
                         "low": np.minimum(o, c) - spread, "close": c}, index=idx)


def test_the_second_replay_agrees_with_the_engine_on_a_real_family():
    from mt5desk.engine import Costs, run_backtest
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    d = _bars(days=400)
    sig = ORTHOGONAL_FAMILIES["vol_transition"](d)
    if len(sig) < 10:
        pytest.skip("family produced too few signals on synthetic bars")
    costs = Costs(spread_per_lot=0.0, commission_per_lot=0.0, contract_oz=100.0)
    bt = run_backtest(d, sig, costs)
    r2 = replay2.replay(d, sig, cost_price_units=0.0)
    cmp = replay2.compare([t.r_multiple for t in bt.trades], [t.r for t in r2])
    assert cmp["ok"], cmp


def test_a_placebo_keeps_the_real_trades_risk_geometry():
    from mt5desk.engine import Signal
    d = _bars()
    atr = redteam._atr_series(d)
    t0 = d.index[1000]
    px, a = float(d["close"].iloc[1000]), float(atr.iloc[1000])
    s = Signal(time=t0, side=1, stop=px - 2 * a, target=px + 3 * a, ttl_bars=8, tag="t",
               trigger=None, wait_bars=1)
    geom = redteam._geometry(d, [s])
    assert geom[t0] == pytest.approx((2.0, 3.0), rel=1e-6)
    moved = redteam._shift(d, atr, geom, [s], 500)[0]
    px2, a2 = float(d["close"].iloc[1500]), float(atr.iloc[1500])
    assert moved.stop == pytest.approx(px2 - 2 * a2, rel=1e-9)
    assert moved.target == pytest.approx(px2 + 3 * a2, rel=1e-9)


def test_the_red_team_distinguishes_a_planted_edge_from_noise():
    from mt5desk.engine import Signal
    np.random.default_rng(4)
    d = _bars(days=400, seed=4)
    c = d["close"].to_numpy().copy()
    # Plant an edge with BOTH sides: alternate bars drift up 0.4% or down 0.4% over the next
    # six bars, and the signal knows which. With one side only, label-shuffling times among
    # the signals is a no-op and cannot test anything.
    picks = np.arange(24 * 40, 24 * 380, 48)
    sides = [1 if k % 2 == 0 else -1 for k in range(len(picks))]
    for i, sd in zip(picks, sides, strict=False):
        c[i + 1:i + 7] *= np.exp(sd * np.linspace(0.0005, 0.004, 6))
        c[i + 7:] *= np.exp(sd * 0.004)
    d = d.assign(close=c, open=np.concatenate([[c[0]], c[:-1]]))
    d = d.assign(high=np.maximum(d["open"], d["close"]) * 1.0005,
                 low=np.minimum(d["open"], d["close"]) * 0.9995)
    atr = redteam._atr_series(d)
    sig = [Signal(time=d.index[i], side=sd, stop=float(c[i]) - sd * 3 * float(atr.iloc[i]),
                  target=float(c[i]) + sd * 6 * float(atr.iloc[i]), ttl_bars=6, tag="t",
                  trigger=None, wait_bars=1) for i, sd in zip(picks, sides, strict=False)]

    def score(sigs):
        rs = [t.r for t in replay2.replay(d, sigs)]
        return float(np.mean(rs)) if rs else float("nan")
    rt = redteam.run(d, sig, score, n_placebo=15)
    assert rt.verdict == "DISTINGUISHED", rt


# ------------------------------------------------------------------------------------------
# Capacity
# ------------------------------------------------------------------------------------------

def test_capacity_scales_with_edge_and_never_raises_a_bound():
    rng = np.random.default_rng(5)
    d = _bars(days=200, seed=5)
    d["tick_volume"] = rng.integers(500, 5000, size=len(d))
    small = capacity("X", d, edge_frac=0.0002, entry_hours=(8,))
    big = capacity("X", d, edge_frac=0.0010, entry_hours=(8,))
    assert small.participation is not None and big.participation is not None
    assert big.participation > small.participation
    b, _why = bound_from_capacity(small, risk_bound=0.05, book_participation_per_unit_heat=0.5)
    assert b <= 0.05
    b2, _ = bound_from_capacity(small, risk_bound=0.05, book_participation_per_unit_heat=None)
    assert b2 == 0.05


def test_capacity_without_volume_is_unmeasured_not_invented():
    d = _bars(days=100)
    c = capacity("X", d, edge_frac=0.0005)
    assert c.participation is None and "tick_volume" in c.why


# ------------------------------------------------------------------------------------------
# Hypothesis graph
# ------------------------------------------------------------------------------------------

def test_the_graph_remembers_a_buried_region_and_charges_it(tmp_path):
    g = Graph(tmp_path / "g.jsonl")
    g.append(Node("XAUUSD", "f", {"lookback": 240, "entry_z": 2.0}, source="s", fate=FAILED,
                  why="failed walk_forward", gates={"walk_forward": {"passed": False}}))
    pf = g.prior_failures("XAUUSD", "f", {"lookback": 280, "entry_z": 2.4})
    assert pf["n_failed"] == 1 and "walk_forward" in pf["gates_failed"]
    assert g.prior_failures("XAUUSD", "f", {"lookback": 400, "entry_z": 2.0})["n_failed"] == 0


def test_regions_coarsen_continuous_params_and_keep_discrete_ones():
    a = region_key("X", "f", {"lookback": 210, "side_mode": "revert"})
    b = region_key("X", "f", {"lookback": 290, "side_mode": "revert"})
    c = region_key("X", "f", {"lookback": 210, "side_mode": "continue"})
    assert a == b != c


def test_a_new_fate_is_a_new_row_and_the_current_view_takes_the_last(tmp_path):
    g = Graph(tmp_path / "g.jsonl")
    n = Node("X", "f", {"k": 1}, fate=BORN)
    g.append(n)
    g.append(Node("X", "f", {"k": 1}, fate=FAILED, why="later"))
    assert len(g.rows()) == 2
    assert g.current()[n.id]["fate"] == FAILED


def test_verdicts_are_recorded_with_the_gates_they_failed(tmp_path):
    g = Graph(tmp_path / "g.jsonl")
    record_verdicts([{"sym": "X", "family": "f", "params": {"k": 1},
                      "gates": {"pbo": {"passed": True}, "lockbox": {"passed": False}}}], graph=g)
    cur = next(iter(g.current().values()))
    assert cur["fate"] == FAILED and "lockbox" in cur["why"]


# ------------------------------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------------------------------

def test_the_manifest_chain_verifies_and_detects_an_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(live_manifest, "CHAIN", tmp_path / "m.jsonl")
    live_manifest.write()
    live_manifest.write()
    assert live_manifest.verify()["ok"]
    lines = (tmp_path / "m.jsonl").read_text("utf-8").splitlines()
    e = json.loads(lines[0])
    e["armed"] = {"armed": False}
    lines[0] = json.dumps(e)
    (tmp_path / "m.jsonl").write_text("\n".join(lines) + "\n", "utf-8")
    v = live_manifest.verify()
    assert not v["ok"] and v["broken_at"] == 0
