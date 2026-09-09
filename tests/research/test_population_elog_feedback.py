"""The populations are ordered by what they were WORTH, not by how many trees they drew (G4).

The weights that decide which population runs first under a short budget were fed by yield
counts -- draws and later certify counts. A count is not a contribution: a population drawing
ten cells the book cannot use outranked one drawing a single tail diversifier, which is the
ordering the whole fitness exists to invert. What is pinned: the realised `delta_elog` of each
population's SCORED draws is reported per population, turned into the next pass's weights with a
floor that keeps a bad hour from retiring anything, and UNMEASURED (uniform) until something has
been scored.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research import search_populations as sp
from libs.research.alpha_fitness import FitnessTerms


def _ctx(**kw) -> sp.SearchContext:
    n = 600
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.001, n))), index=idx)
    frames = {"close": close, "ret": np.log(close).diff(),
              "range": pd.Series(0.001, index=idx), "activity": pd.Series(100.0, index=idx)}
    return sp.SearchContext(rng=np.random.default_rng(1), frames=frames, ret=frames["ret"],
                            symbol="EURUSD", allow_drivers=False, **kw)


def test_a_population_reports_the_realised_growth_of_its_scored_draws() -> None:
    ctx = _ctx(attributed=[("gp", FitnessTerms(delta_elog=2.0)),
                           ("gp", FitnessTerms(delta_elog=4.0)),
                           ("symreg", FitnessTerms(delta_elog=-1.0))])
    res = sp.run(ctx, n_per_population=1, budget_s=30.0, names=["gp", "symreg", "bayesian"])
    assert res.yields["gp"].delta_elog_mean == pytest.approx(3.0)
    assert res.yields["gp"].scored == 2
    assert res.yields["symreg"].delta_elog_mean == pytest.approx(-1.0)
    # A population nothing has scored is UNMEASURED, not zero: "not yet judged" and "judged
    # worthless" are opposite facts.
    assert res.yields["bayesian"].delta_elog_mean is None
    assert res.yields["bayesian"].scored == 0
    row = next(r for r in res.yield_rows() if r["population"] == "gp")
    assert row["delta_elog_mean"] == pytest.approx(3.0) and row["scored"] == 2


def test_the_weights_rank_by_growth_and_never_retire_a_population() -> None:
    ctx = _ctx(attributed=[("gp", FitnessTerms(delta_elog=5.0)),
                           ("symreg", FitnessTerms(delta_elog=-5.0)),
                           ("bayesian", FitnessTerms(delta_elog=0.0))])
    res = sp.run(ctx, n_per_population=1, budget_s=30.0,
                 names=["gp", "symreg", "bayesian"])
    w, basis = res.elog_weights()
    assert w is not None
    assert w["gp"] > w["bayesian"] >= w["symreg"], w
    assert min(w.values()) >= sp.ELOG_FLOOR > 0.0, (
        "a population below the pooled mean keeps the floor: the ordering is a preference, "
        "never a retirement")
    assert "realised dE[logW]" in basis and "pooled mean" in basis and "gp" in basis
    # And the ordering those weights produce still contains every named population.
    order = sp._order(["gp", "symreg", "bayesian"], w, np.random.default_rng(2))
    assert sorted(order) == ["bayesian", "gp", "symreg"]


def test_nothing_scored_is_unmeasured_and_leaves_the_callers_table_standing() -> None:
    res = sp.run(_ctx(), n_per_population=1, budget_s=20.0, names=["gp", "symreg"])
    w, basis = res.elog_weights()
    assert w is None and "unmeasured" in basis
    assert all(y.delta_elog_mean is None for y in res.yields.values())


def test_a_non_finite_growth_is_dropped_rather_than_poisoning_the_mean() -> None:
    ctx = _ctx(attributed=[("gp", FitnessTerms(delta_elog=float("nan"))),
                           ("gp", FitnessTerms(delta_elog=1.0)),
                           ("symreg", FitnessTerms(delta_elog=float("inf")))])
    res = sp.run(ctx, n_per_population=1, budget_s=30.0, names=["gp", "symreg"])
    assert res.yields["gp"].delta_elog_mean == pytest.approx(1.0) and res.yields["gp"].scored == 1
    assert res.yields["symreg"].delta_elog_mean is None
    w, _basis = res.elog_weights()
    assert w is not None and all(np.isfinite(v) for v in w.values())


def test_the_evolution_feeds_the_weights_back_between_draws() -> None:
    """The organ's loop: attribute what was scored, ask for the weights, use them next draw."""
    import inspect
    import sys
    from pathlib import Path

    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import alpha_evolution as ae

    src = inspect.getsource(ae.evolve)
    assert "ctx.attributed" in src, "the populations are not told what their draws were worth"
    assert "res.elog_weights()" in src
    assert "live_weights[0] if live_weights[0] else pop_weights" in src, (
        "the realised-growth ordering must supersede the file's table once it exists")
