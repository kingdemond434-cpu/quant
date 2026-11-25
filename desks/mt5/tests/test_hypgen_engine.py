"""The four generated model families and the engine that proposes them: causal, charged, spread."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hypgen_engine as he  # noqa: E402
import mt5desk.families_orthogonal  # noqa: E402,F401
from mt5desk import family_hypgen_models as fm  # noqa: E402
from mt5desk import hypgen_features as hf  # noqa: E402
from mt5desk.families import get_family_func  # noqa: E402

META = {"EURUSD": {"contract_size": 100000, "tick_size": 0.00001, "tick_value": 1.0,
                   "median_spread_pts": 10}}


def _bars(n: int = 3000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n, freq="h", tz="UTC")
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    o = np.concatenate([[c[0]], c[:-1]])
    hi = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 3e-4, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 3e-4, n)))
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c,
                         "tick_volume": rng.integers(100, 1000, n).astype(float)}, index=idx)


def test_features_are_causal():
    d = _bars(1500)
    full = hf.matrix(d, hf.FEATURES)
    part = hf.matrix(d.iloc[:1000], hf.FEATURES)
    assert np.allclose(full[:1000], part, equal_nan=True)


def test_forward_label_only_reads_the_future_it_names():
    d = _bars(200)
    y = hf.forward_log_return(d, 5)
    o = np.log(d["open"].to_numpy())
    assert np.isclose(y[10], o[16] - o[11]) and np.isnan(y[-6:]).all()


def _net():
    return {"inputs": ["ret_1", "z_20"], "hidden": {"h500": "tanh"},
            "conns": [["i0", "h500", 1.2, True], ["h500", "out", -0.8, True],
                      ["i1", "out", 0.6, True]]}


SIDES = {
    "knn": lambda d: fm.knn_sides(d, ["ret_1", "ret_4", "z_20"], 10, 4, 300, 1.0, 1),
    "rank": lambda d: fm.rank_sides(d, ["ret_1", "z_20", "rsi_14"], 4, 300, 50, 0.8),
    "ge": lambda d: fm.rule_sides(d, {"op": "or", "a": {"op": "block", "b": "breakout",
                                                        "p": {"n": 20}},
                                      "b": {"op": "not", "a": {"op": "block", "b": "rsi",
                                                               "p": {"n": 2, "lo": 10}}}}),
}


@pytest.mark.parametrize("name", sorted(SIDES))
def test_model_families_have_no_lookahead(name):
    d = _bars(1400, seed=4)
    cut = 1100
    full = SIDES[name](d)
    part = SIDES[name](d.iloc[:cut])
    assert np.array_equal(full[:cut], part)


def test_neural_policy_has_no_lookahead_and_refuses_cycles():
    d = _bars(1400, seed=4)
    x_full = hf.matrix(d, ["ret_1", "z_20"])
    x_part = hf.matrix(d.iloc[:1100], ["ret_1", "z_20"])
    assert np.allclose(fm.net_forward(_net(), x_full)[:1100], fm.net_forward(_net(), x_part))
    cyc = _net()
    cyc["conns"].append(["out", "h500", 1.0, True])
    assert fm.net_forward(cyc, x_full) is None


@pytest.mark.parametrize("fam,params", [
    ("analog_knn", {"features": ["ret_1", "z_20"], "k": 10, "h": 4, "library": 300, "thr": 0.5}),
    ("ranked_linear", {"features": ["ret_1", "z_20"], "h": 4, "window": 300, "refit": 50,
                       "q": 0.8}),
    ("neural_policy", {"net": _net(), "thr": 0.1}),
    ("ge_strategy", {"rule": {"op": "block", "b": "breakout", "p": {"n": 10}},
                     "bank_frac": 0.5, "runner_trail_k": 2.0}),
])
def test_families_emit(fam, params):
    sigs = get_family_func(fam)(_bars(1500), **params)
    assert sigs and all(s.side in (-1, 1) for s in sigs)


@pytest.mark.parametrize("seat", sorted(he.SPACES))
def test_space_operators_stay_valid(seat):
    sp = he.SPACES[seat]
    rng = random.Random(2)  # noqa: S311
    pop = [sp.random(rng, rng.choice(list(sp.classes))) for _ in range(20)]
    assert all(sp.valid(g) for g in pop)
    ok = 0
    for _ in range(150):
        c = sp.mutate(rng, sp.crossover(rng, rng.choice(pop), rng.choice(pop)))
        ok += sp.valid(c)
        if sp.valid(c):
            assert sp.mech_class(c) in set(sp.classes) | {"other"}
            assert sp.params(c)
    assert ok > 100


def test_ge_decodes_deterministically_and_steers_class():
    sp = he.SPACES["ge_builder"]
    rng = random.Random(5)  # noqa: S311
    g = sp.random(rng, "reversion")
    assert sp.params(g) == sp.params(json.loads(json.dumps(g)))
    assert sp.mech_class(g) == "reversion"


def test_neat_mutation_keeps_the_graph_acyclic():
    sp = he.SPACES["neat_evolver"]
    rng = random.Random(9)  # noqa: S311
    g = sp.random(rng)
    x = hf.matrix(_bars(400), g["net"]["inputs"])
    for _ in range(300):
        g = sp.mutate(rng, g)
        assert fm.net_forward(g["net"], x) is not None


@pytest.mark.parametrize("seat", sorted(he.SPACES))
def test_noise_is_not_proposed(tmp_path, monkeypatch, seat):
    monkeypatch.setattr(he.sb, "JUDGING_RATE", tmp_path / "absent.json")
    monkeypatch.setattr(he, "POP", 8)
    loader = lambda s, c: _bars(4000, seed=11)  # noqa: E731
    rep = he.run(he.SPACES[seat], budget_s=600, symbols=["EURUSD"], chart="H1", dry_run=True,
                 state_dir=tmp_path, loader=loader, meta={"symbols": META}, seed=3,
                 max_generations=2)
    assert rep["cells"]["EURUSD|H1"]["evaluated_pass"] > 0
    assert rep["survivors"] == 0


def _one_survivor(monkeypatch, space):
    def harvest(self):
        a = {"g": space.random(random.Random(1)), "fit": 1.0}  # noqa: S311
        return [self._row(a, np.full(30, 0.2), 0.99, 0.001, 50, max(self.evaluated_total, 1))]
    monkeypatch.setattr(he.ModelLineage, "harvest", harvest)


def test_no_charge_no_donation_then_charged_donation(tmp_path, monkeypatch):
    import proposer_common

    from libs.research import claim_selection
    space = he.SPACES["ge_builder"]
    _one_survivor(monkeypatch, space)
    calls = []
    monkeypatch.setattr(proposer_common, "donate", lambda *a, **k: calls.append(a) or tmp_path)
    monkeypatch.setattr(he.sb, "JUDGING_RATE", tmp_path / "absent.json")
    monkeypatch.setattr(he, "REPORTS", tmp_path)
    monkeypatch.setattr(he, "POP", 6)

    def boom(rows):
        raise OSError("disk full")
    monkeypatch.setattr(claim_selection, "register_grid", boom)
    loader = lambda s, c: _bars(3000, seed=5)  # noqa: E731
    rep = he.run(space, budget_s=600, symbols=["EURUSD"], chart="H1", state_dir=tmp_path,
                 loader=loader, meta={"symbols": META}, seed=1, max_generations=1)
    assert calls == [] and rep["donated"] == 0
    assert json.loads((tmp_path / "EURUSD_H1.json").read_text())["proposed"] == []
    monkeypatch.setattr(claim_selection, "register_grid",
                        lambda rows: {"claim_families": {r["claim_family"]: {} for r in rows}})
    rep = he.run(space, budget_s=600, symbols=["EURUSD"], chart="H1", state_dir=tmp_path,
                 loader=loader, meta={"symbols": META}, seed=2, max_generations=1)
    assert len(calls) == 1 and rep["donated"] == 1
    row = calls[0][1][0]
    assert row["family"] == "ge_strategy" and "rule" in row["params"]
    assert row["claim_selection_trials"] >= 1 and row["claim_family"].startswith("claim:")


def test_corrupt_state_is_skipped_and_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(he.sb, "JUDGING_RATE", tmp_path / "absent.json")
    monkeypatch.setattr(he, "REPORTS", tmp_path)
    bad = tmp_path / "EURUSD_H1.json"
    bad.write_text('{"evaluated_total": 777, "pop": [')
    before = bad.read_bytes()
    rep = he.run(he.SPACES["knn_analog"], budget_s=60, symbols=["EURUSD"], chart="H1",
                 state_dir=tmp_path, loader=lambda s, c: _bars(3000), meta={"symbols": META},
                 seed=1, max_generations=1)
    assert "unreadable" in rep["cells"]["EURUSD|H1"]["skipped"]
    assert bad.read_bytes() == before


def test_each_seat_has_its_own_claim_family():
    from mt5desk.engine import Costs
    ids = set()
    for sp in he.SPACES.values():
        lin = he.ModelLineage(sp, "EURUSD", "H1", _bars(3000),
                              Costs.from_symbol(META["EURUSD"], mult=2.0), seed=1,
                              state_dir=Path("/nonexistent") / sp.seat)
        ids.add(lin.claim_family)
    assert len(ids) == len(he.SPACES)
