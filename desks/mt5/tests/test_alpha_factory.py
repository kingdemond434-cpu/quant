"""The alpha grammar, the formula family, the genetic proposer and the research bandit.

What is pinned:

  * every expression the grammar can produce is causal: its value at bar t is identical whether
    or not the bars after t exist (the lookahead falsifier, run over random trees);
  * evaluation never raises -- an unknown terminal, a missing driver, a window longer than the
    history all yield NaN, and the family turns NaN into "no signal";
  * mutation and crossover only ever produce valid trees, and the recipe is plain JSON;
  * the formula family follows or fades an extreme z-score and refuses an expression that names
    a driver it was not given;
  * the evolution charges every expression it tried, including the ones successive halving
    culled, and proposes nothing that does not clear cost and deflation;
  * the bandit is uniform-ish when cold (price alone cannot allocate), moves budget to the arm
    that certifies, and never starves an arm below the exploration floor.
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

from mt5desk.family_formula import family_formula  # noqa: E402

from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import bandit  # noqa: E402
from research import alpha_evolution  # noqa: E402


def _bars(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06", periods=n, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(scale=0.1, size=n))
    high = close + rng.uniform(0.02, 0.15, n)
    low = close - rng.uniform(0.02, 0.15, n)
    open_ = np.r_[close[0], close[:-1]]
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "tick_volume": rng.integers(50, 500, n).astype(float),
                       "spread": rng.integers(10, 20, n).astype(float)}, index=idx)
    df.index.name = "time"
    return df


# --------------------------------------------------------------------------- grammar
def test_every_random_tree_is_valid_and_json() -> None:
    rng = np.random.default_rng(1)
    for _ in range(200):
        e = ag.random_expr(rng, 3)
        assert ag.is_valid(e), ag.to_str(e)
        assert json.loads(json.dumps(e)) == e
        assert ag.complexity(e) >= 1 and ag.depth(e) <= ag.MAX_DEPTH


def test_mutation_and_crossover_preserve_validity() -> None:
    rng = np.random.default_rng(2)
    for _ in range(150):
        a, b = ag.random_expr(rng, 3), ag.random_expr(rng, 3)
        assert ag.is_valid(ag.mutate(a, rng))
        assert ag.is_valid(ag.crossover(a, b, rng))
    a = ag.random_expr(rng, 3, allow_drivers=False)
    for _ in range(50):
        a = ag.mutate(a, rng, allow_drivers=False)
        assert not (ag.terminals_in(a) & set(ag.DRIVER_TERMINALS))


def test_every_operator_is_causal() -> None:
    """The lookahead falsifier: the value at bar t must not change when bars after t are
    removed. Run over random trees and every canonical alpha."""
    df = _bars(1500)
    cut = 1100
    frames_full = ag.terminal_frames(df, raw=df)
    frames_cut = ag.terminal_frames(df.iloc[:cut], raw=df.iloc[:cut])
    rng = np.random.default_rng(3)
    exprs = list(ag.CANON.values()) + [ag.random_expr(rng, 3, allow_drivers=False)
                                       for _ in range(60)]
    for e in exprs:
        a = ag.evaluate(e, frames_full).iloc[:cut].to_numpy()
        b = ag.evaluate(e, frames_cut).to_numpy()
        both = np.isfinite(a) & np.isfinite(b)
        assert (np.isfinite(a) == np.isfinite(b)).all(), ag.to_str(e)
        assert np.allclose(a[both], b[both], rtol=1e-9, atol=1e-12), ag.to_str(e)


def test_evaluation_never_raises_and_undefined_is_nan() -> None:
    df = _bars(400)
    frames = ag.terminal_frames(df, raw=df)
    assert ag.evaluate("usd", frames).isna().all()                       # driver not given
    assert ag.evaluate(["mean", "close", 240], frames).isna().sum() >= 239
    assert ag.evaluate(["div", "close", ["sub", "close", "close"]], frames).isna().all()
    assert ag.evaluate(["nonsense", "close"], frames).isna().all()
    assert ag.evaluate(["mean", "close", 10_000], frames).isna().all()  # window > history
    assert ag.evaluate(["corr", "close", "activity", 48], frames).notna().sum() > 300


def test_driver_terminals_are_aligned_causally() -> None:
    df = _bars(600)
    drv = _bars(600, seed=9).iloc[::3]                                 # sparser driver clock
    frames = ag.terminal_frames(df, raw=df, drivers={"usd": drv})
    s = frames["usd"]
    # At each bar the driver value is its last close at or before that bar, never a later one.
    for ts in df.index[100:110]:
        prior = drv["close"][drv.index <= ts]
        assert s[ts] == prior.iloc[-1]


def test_describe_names_what_the_tree_computes() -> None:
    d = ag.describe(["zscore", ["delta", "close", 24], 120], "fade")
    assert "zscore(delta(close, 24), 120)" in d and "faded" in d and "close" in d


# --------------------------------------------------------------------------- formula family
def test_formula_follows_and_fades_an_extreme_z() -> None:
    df = _bars(4000, seed=5)
    expr = ["delta", "close", 24]
    follow = family_formula(df, expr=expr, norm=240, entry_z=2.0, side_mode="follow")
    fade = family_formula(df, expr=expr, norm=240, entry_z=2.0, side_mode="fade")
    assert follow and fade
    by_time = {s.time: s.side for s in follow}
    for s in fade:
        assert by_time[s.time] == -s.side                       # same bars, opposite sides
    for s in follow:
        assert (s.target - s.stop) * s.side > 0 and s.tag == "formula:follow"
    frames = ag.terminal_frames(df, raw=df)
    z = ag.evaluate(expr, frames)
    r = z.rolling(240, min_periods=240)
    zz = (z - r.mean()) / r.std()
    for s in follow[:20]:
        assert abs(zz[s.time]) >= 2.0 and np.sign(zz[s.time]) == s.side


def test_formula_refuses_without_the_driver_it_names() -> None:
    df = _bars(2000)
    assert family_formula(df, expr=["corr", "ret", "usd", 48]) == []
    assert family_formula(df, expr=["corr", "ret", "usd", 48],
                          drivers={"usd": _bars(2000, seed=4)}) != []
    assert family_formula(df, expr=None) == []
    assert family_formula(df, expr=["bogus", "close"]) == []
    assert family_formula(df, expr="close", side_mode="sideways") == []


# --------------------------------------------------------------------------- evolution
def test_evolution_charges_every_expression_and_proposes_only_survivors(monkeypatch) -> None:
    df = _bars(3500, seed=7)
    ev = alpha_evolution.evolve("SYN", df, cost=0.0002, drivers={}, survivors=None, seed=1,
                                budget_s=120.0, pop=8, gens=2)
    rows = list(ev.rows.values())
    assert len(rows) >= 8
    assert all("fitness" in r for r in rows)
    assert any(r.get("stage") == 1 for r in rows)                  # the better half went full
    from research import proposer_common as pc
    deflated = pc.deflate(rows)
    assert all(r["n_tests_sweep"] == len(rows) for r in deflated)   # culled rows still charged
    for r in deflated:
        if r.get("stage") != 1:
            r["proposed"] = False
    for r in pc.best_per_cell(deflated):
        assert r["clears_cost"] and r["t_deflated_sweep"] > pc.PROPOSE_T


def test_daily_pnl_proxy_signs_with_the_position() -> None:
    idx = pd.date_range("2025-01-01", periods=48, freq="h", tz="UTC")
    z = pd.Series(0.0, index=idx)
    z.iloc[10] = 3.0                                                # long from bar 10
    ret = pd.Series(0.01, index=idx)
    pnl = alpha_evolution._daily_pnl_proxy(z, ret, entry_z=2.0, hold=4)
    assert pnl.sum() == pytest.approx(0.04)                        # held 4 bars of +1%


# --------------------------------------------------------------------------- bandit
def _rows(arm_source: str, failed: int, certified: int) -> list[dict]:
    out = []
    for i in range(failed):
        out.append({"id": f"{arm_source}f{i}", "source": arm_source, "fate": "FAILED"})
    for i in range(certified):
        out.append({"id": f"{arm_source}c{i}", "source": arm_source, "fate": "CERTIFIED"})
    return out


def test_cold_bandit_is_near_uniform_and_never_starves_an_arm() -> None:
    ev = bandit.evidence([])
    shares = bandit.allocate({a: ev[a] for a in bandit.ARMS}, np.random.default_rng(0))
    assert abs(sum(shares.values()) - 1.0) < 1e-3                 # rounded to 4 places
    floor = bandit.EXPLORE / len(bandit.ARMS)
    assert all(s >= floor - 1e-9 for s in shares.values())
    assert max(shares.values()) < 0.25                             # price alone cannot allocate


def test_bandit_moves_budget_to_the_arm_that_certifies(monkeypatch) -> None:
    # Equal declared costs, so the ordering is evidence alone (the cost table is a separate,
    # declared input and is exercised by the cold-start test above).
    monkeypatch.setattr(bandit, "COST", dict.fromkeys(bandit.ARMS, (1.0, 1.0, 1.0, 1.0)))
    rows = _rows("alpha_evolution", failed=40, certified=12) + \
        _rows("crawler", failed=200, certified=1) + _rows("excursions", failed=30, certified=0)
    ev = bandit.evidence(rows)
    assert ev["new_mechanism"]["certified"] == 12 and ev["alt_data_hypothesis"]["failed"] == 200
    shares = bandit.allocate({a: ev[a] for a in bandit.ARMS}, np.random.default_rng(0))
    assert shares["new_mechanism"] > shares["alt_data_hypothesis"]
    assert shares["new_mechanism"] > shares["exit_improvement"]
    assert shares["new_mechanism"] == max(shares.values())


def test_arm_mapping_and_weights(tmp_path, monkeypatch) -> None:
    assert bandit.arm_of("regime_coverage") == "conditional_state_edge"
    assert bandit.arm_of("anything", kind="exit_hypothesis") == "exit_improvement"
    assert bandit.arm_of("no_such_source") == "alt_data_hypothesis"
    monkeypatch.setattr(bandit, "BUDGET", tmp_path / "budget.json")
    bandit._CACHE["mtime"] = None
    assert bandit.arm_weight("regime_coverage") == pytest.approx(1.0)    # no budget: uniform
    (tmp_path / "budget.json").write_text(json.dumps(
        {"shares": {a: (0.5 if a == "exit_improvement" else 0.5 / (len(bandit.ARMS) - 1))
                    for a in bandit.ARMS}}))
    bandit._CACHE["mtime"] = None
    # weight = share x number of arms, so half the budget on one of N arms is N/2.
    assert bandit.arm_weight("excursions") == pytest.approx(0.5 * len(bandit.ARMS))
