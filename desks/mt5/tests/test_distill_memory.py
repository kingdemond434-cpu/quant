"""The survivor prior, the mutation ledger and the typed memory, on synthetic ground.

    cd desks/mt5 && python3 -m pytest tests/test_distill_memory.py -q

Everything here runs off-box against files written to tmp_path: a hypothesis graph appended
through the real `Graph`, a survivors canon shaped like the desk's, a toy family registered in
the real registry, synthetic H1 bars in a private universe dir. No network, no real ledger is
touched -- `donate` (which pre-registers into a real JSONL) is replaced by a recorder.

WHAT MUST NOT REGRESS:

  1. every screened mutation is a counted trial, including the ones with too few trades
  2. a neighbour whose node the graph already holds is never proposed again
  3. a candidate leaves with its parent certificate and operator on its evidence
  4. a missing input is a recorded reason, never a silent empty report
  5. memory is idempotent, and a worker's prompt context surfaces the corpse
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

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

from libs.research import memory as mem  # noqa: E402
from libs.research.hypothesis_graph import Graph, Node, node_id  # noqa: E402
from research import mutation_yield as my  # noqa: E402
from research import proposer_common as pc  # noqa: E402
from research import regime_coverage as rc  # noqa: E402
from research import survivor_distiller as sd  # noqa: E402

FAM = "toy"


# ------------------------------------------------------------------------------------------
# Synthetic ground
# ------------------------------------------------------------------------------------------

def _bars(n: int = 4000, drift: float = 2e-4, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    r = rng.normal(drift, 1e-3, n)
    close = 1.0 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[1.0], close[:-1]])
    hi = np.maximum(open_, close) * (1 + rng.uniform(0, 5e-4, n))
    lo = np.minimum(open_, close) * (1 - rng.uniform(0, 5e-4, n))
    return pd.DataFrame({"open": open_, "high": hi, "low": lo, "close": close,
                         "tick_volume": 100.0}, index=idx)


def toy_family(df: pd.DataFrame, *, feature: str = "x", band=(0.75, 0.9), horizon: int = 3,
               side: int = 1, every: int = 12) -> list[Signal]:
    """A signal every `every` bars, held `horizon` bars: enough trades to screen, and a
    parameterisation the distiller can step (numeric list, int, categorical side)."""
    out = []
    for i in range(50, len(df) - 1, every):
        px = float(df["close"].iloc[i])
        out.append(Signal(time=df.index[i], side=int(side), stop=px * 0.99, target=px * 1.01,
                          ttl_bars=int(horizon), tag=FAM))
    return out


def _cert(sym: str, params: dict, key: str | None = None) -> tuple[str, dict]:
    key = key or f"external.{sym}.{FAM}.p={node_id(sym, FAM, params)}"
    return key, {"hunt": "external_discoveries", "cell": f"{sym}.{FAM}", "sym": sym,
                 "days": 900, "gated_at": "2026-08-25T22:00:42+00:00",
                 "gates": {"economic_prior": {"passed": True, "message": "a toy mechanism"},
                           "lockbox": {"passed": True}},
                 "shadow_spec": {"symbol": sym, "family": FAM, "selector": "asia",
                                 "condition": None, "params": params}}


def _write_canon(path: Path, certs: list[tuple[str, dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n": len(certs), "survivors": dict(certs)}), "utf-8")


@pytest.fixture
def ground(tmp_path, monkeypatch):
    """A private desk: graph, canon, universe, reports, queue, weights -- all under tmp_path."""
    data = tmp_path / "desks" / "mt5" / "data"
    uni = data / "universe"
    uni.mkdir(parents=True)
    _bars().to_parquet(uni / "TOYUSD_H1.parquet")
    _bars(n=1200, seed=1).to_parquet(uni / "SHORTUSD_H1.parquet")
    graph_path = data / "hypothesis_graph.jsonl"
    g = Graph(graph_path)
    # Failures thin out where survivors sit: the survivors hold horizon 3, failures 10-24.
    # Distinct params per row: the graph is append-only and keys on the node, so two rows with
    # the same params are one node's history, not two failures.
    for i, h in enumerate((10, 12, 24)):
        g.append(Node("TOYUSD", FAM, {"feature": "x", "band": [0.25, 0.5], "horizon": h,
                                      "side": 1}, source="external", fate="FAILED",
                      why=f"failed stress_costs #{i}", at=f"2026-08-0{i + 1}T00:00:00+00:00"))
    g.append(Node("TOYUSD", FAM, {"feature": "x", "band": [0.75, 0.9], "horizon": 1, "side": 1},
                  source="external", fate="CERTIFIED", why="canonical verdict PASSED",
                  at="2026-08-20T00:00:00+00:00"))
    certs = [_cert("TOYUSD", {"feature": "x", "band": [0.75, 0.9], "horizon": 6, "side": 1}),
             _cert("TOYUSD", {"feature": "x", "band": [0.75, 0.9], "horizon": 3, "side": 1}),
             _cert("NOBARS", {"feature": "x", "band": [0.75, 0.9], "horizon": 3, "side": -1}),
             _cert("SHORTUSD", {"feature": "x", "band": [0.75, 0.9], "horizon": 3, "side": 1})]
    canon = data / "UNIVERSAL_SURVIVORS.canon.json"
    _write_canon(canon, certs)
    reports = tmp_path / "desks" / "mt5" / "reports"
    reports.mkdir(parents=True)
    queue = data / "hypotheses" / "miner_deepening_queue.json"
    donated: list[dict] = []

    def _donate(source, cands, tests_run):
        donated.append({"source": source, "candidates": cands, "tests_run": tests_run})
        return tmp_path / f"discoveries_{source}.json"

    monkeypatch.setattr(sd, "CANON", canon)
    monkeypatch.setattr(sd, "GRAPH", graph_path)
    monkeypatch.setattr(sd, "REPORT", reports / "SURVIVOR_DISTILLER.json")
    monkeypatch.setattr(sd, "WEIGHTS", data / "mutation_operator_weights.json")
    monkeypatch.setattr(my, "CANON", canon)
    monkeypatch.setattr(my, "GRAPH", graph_path)
    monkeypatch.setattr(my, "INTEL", data / "intelligence")
    monkeypatch.setattr(my, "REPORT", reports / "MUTATION_YIELD.json")
    monkeypatch.setattr(my, "OPERATOR_WEIGHTS", data / "mutation_operator_weights.json")
    monkeypatch.setattr(my, "GENERATOR_WEIGHTS", data / "generator_weights.json")
    monkeypatch.setattr(pc, "UNI", uni)
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 1e-5)
    monkeypatch.setattr(pc, "artifact_hours", lambda d: {})
    monkeypatch.setattr(pc, "donate", _donate)
    monkeypatch.setattr(rc, "QUEUE", queue)
    monkeypatch.setitem(fo.ORTHOGONAL_FAMILIES, FAM, toy_family)
    import libs.research.experiment_ledger as el
    monkeypatch.setattr(el, "family_trials", lambda fam, **kw: 0)
    return type("G", (), {"root": tmp_path, "data": data, "graph": g, "canon": canon,
                          "certs": certs, "queue": queue, "donated": donated,
                          "reports": reports})


# ------------------------------------------------------------------------------------------
# 1. the survivor prior and the neighbours
# ------------------------------------------------------------------------------------------

def test_prior_separates_survivor_params_from_failed_ones(ground):
    skipped: dict = {}
    current = sd._current(ground.graph.rows())
    certified = sd.load_certified(json.loads(ground.canon.read_text()), current, skipped)
    failed = [r for r in current.values() if r["fate"] == "FAILED"]
    prior = sd.survivor_prior(certified, failed)
    h = prior[FAM]["horizon"]
    assert h["certified"]["median"] == 3.0 and h["failed"]["median"] == 12.0
    assert h["separation"] > 0
    assert prior[FAM]["band.0"]["certified"]["median"] == 0.75
    # the graph's own CERTIFIED node joins the canon's certificates, once
    assert len(certified) == 5 and len({c["id"] for c in certified}) == 5
    mot = sd.motifs(certified)[FAM]
    assert mot["hold_clusters"]["horizon"]["3"] == 3
    assert mot["session_clusters"] == {"selector=asia": 4}
    assert ["side=1", 4] in mot["categorical"]


def test_neighbours_step_toward_the_survivor_median_and_never_into_history(ground):
    skipped: dict = {}
    rows = ground.graph.rows()
    current = sd._current(rows)
    certified = sd.load_certified(json.loads(ground.canon.read_text()), current, skipped)
    prior = sd.survivor_prior(certified, [r for r in current.values() if r["fate"] == "FAILED"])
    grid = sd.grid_values(rows + certified)
    existing = set(current) | {c["id"] for c in certified}
    parent = next(c for c in certified if c["params"]["horizon"] == 6 and c["symbol"] == "TOYUSD")
    ns = sd.neighbours_of(parent, prior, grid, {}, sd._survivor_values(certified), existing)
    assert 0 < len(ns) <= sd.K_NEIGHBOURS
    ops = {n["operator"] for n in ns}
    assert all(o.startswith(("step_", "swap_")) for o in ops)
    # horizon 6 sits above the survivor median 3, so the horizon step would go DOWN -- onto 3,
    # which is the other certificate. History is not a neighbour: neither direction is emitted.
    assert "step_horizon_down" not in ops and "step_horizon_up" not in ops
    assert all(n["id"] not in existing for n in ns)
    # from a synthetic parent at horizon 24 the down-step lands on the desk's grid (12, a
    # failed row's value), not on an arbitrary fraction of 24
    far = {**parent, "params": {**parent["params"], "horizon": 24}}
    far["id"] = node_id("TOYUSD", FAM, far["params"])
    ns2 = sd.neighbours_of(far, prior, grid, {}, sd._survivor_values(certified), existing)
    down = [n for n in ns2 if n["operator"] == "step_horizon_down"]
    assert down and down[0]["params"]["horizon"] == 12
    assert "step_horizon_up" not in {n["operator"] for n in ns2}
    assert all(n["parent"] == parent["key"] and n["family"] == FAM for n in ns2)


def test_operator_weights_bias_which_parameter_is_perturbed_first(ground):
    skipped: dict = {}
    rows = ground.graph.rows()
    current = sd._current(rows)
    certified = sd.load_certified(json.loads(ground.canon.read_text()), current, skipped)
    prior = sd.survivor_prior(certified, [r for r in current.values() if r["fate"] == "FAILED"])
    grid = sd.grid_values(rows + certified)
    parent = next(c for c in certified if c["params"]["horizon"] == 6 and c["symbol"] == "TOYUSD")
    sv = sd._survivor_values(certified)
    plain = sd.neighbours_of(parent, prior, grid, {}, sv, set(), k=1)
    biased = sd.neighbours_of(parent, prior, grid, {"swap_side": 4.0}, sv, set(), k=1)
    assert plain[0]["operator"] != "swap_side"
    assert biased[0]["operator"] == "swap_side"
    assert biased[0]["params"]["side"] == -1         # the NOBARS survivor's side, swapped in
    # the weights file is read the way mutation_yield writes it: numeric keys, "_" meta ignored
    sd.WEIGHTS.write_text(json.dumps({"step_horizon_down": 2.5, "_reason": "x", "_clip": [1]}))
    w, note = sd._weights()
    assert w == {"step_horizon_down": 2.5} and "1 operator weights" in note


# ------------------------------------------------------------------------------------------
# 2. the run: screen, count, deflate, donate, queue, degrade
# ------------------------------------------------------------------------------------------

def test_run_counts_every_trial_and_donates_with_parent_and_operator(ground):
    rep = sd.run(budget_s=60.0)
    assert rep["certified_cells"] == 5 and rep["neighbours_generated"] > 0
    assert rep["tests_run"] > 0
    assert sd.REPORT.exists()
    written = json.loads(sd.REPORT.read_text())
    assert set(written) >= {"prior", "motifs", "tests_run", "cells_proposed", "skipped"}
    # every proposal was deflated by the WHOLE sweep, and cleared the shared bar
    for p in rep["proposals"]:
        assert p["n_tests_sweep"] == rep["tests_run"]
        assert p["t_deflated_sweep"] > pc.PROPOSE_T and p["clears_cost"]
        assert p["n_independent"] >= pc.MIN_TRADES
    # the toy drift is positive, so a long neighbour clears; the donation carries lineage
    assert rep["cells_proposed"] >= 1
    assert ground.donated and ground.donated[0]["source"] == sd.SOURCE
    assert ground.donated[0]["tests_run"] == rep["tests_run"]
    for c in ground.donated[0]["candidates"]:
        assert c["evidence"]["parent"] in dict(ground.certs)
        assert c["evidence"]["operator"].startswith(("step_", "swap_"))
        assert c["mechanism"].endswith(f"(mutation: {c['evidence']['operator']})")
        assert c["family"] == FAM and c["source"] == sd.SOURCE
    # the symbol with no bars became deepening tasks of kind "mutation", owned by this source
    assert rep["skipped"]["NOBARS"] == "no H1 bars on this box"
    assert rep["skipped"]["SHORTUSD"].startswith("under")
    q = json.loads(ground.queue.read_text())["tasks"]
    mine = [t for t in q if t["source"] == sd.SOURCE]
    assert mine and len(mine) == rep["n_tasks"] <= sd.MAX_TASKS
    assert {t["kind"] for t in mine} == {"mutation"}
    assert {t["symbols"][0] for t in mine} == {"NOBARS", "SHORTUSD"}
    for t in mine:
        assert t["family"] == FAM and t["status"] is None and t["params"] and t["parent"]
        assert t["operator"] in t["title"]


def test_a_screen_with_too_few_trades_is_still_a_counted_trial(ground, monkeypatch):
    def sparse(df, **params):
        return toy_family(df, **{**params, "every": 900})   # ~4 trades: under MIN_TRADES
    monkeypatch.setitem(fo.ORTHOGONAL_FAMILIES, FAM, sparse)
    rep = sd.run(budget_s=60.0)
    assert rep["tests_run"] > 0 and rep["cells_proposed"] == 0
    assert not ground.donated
    # nothing was proposed, yet every looked-at mutation was billed to the sweep
    assert rep["by_operator"] and sum(rep["by_operator"].values()) == rep["tests_run"]


def test_a_family_that_emits_nothing_is_a_recorded_skip_not_a_trial(ground, monkeypatch):
    monkeypatch.setitem(fo.ORTHOGONAL_FAMILIES, FAM, lambda df, **p: [])
    rep = sd.run(budget_s=60.0)
    assert rep["tests_run"] == 0
    assert any(v == "family produced no signals" for v in rep["skipped"].values())


def test_missing_canon_and_graph_degrade_with_reasons(ground, monkeypatch):
    monkeypatch.setattr(sd, "CANON", ground.data / "nope.json")
    monkeypatch.setattr(sd, "GRAPH", ground.data / "nope.jsonl")
    rep = sd.run(budget_s=5.0)
    assert rep["certified_cells"] == 0 and rep["tests_run"] == 0
    assert "no survivors canon" in rep["skipped"]["canon"]
    assert "no rows" in rep["skipped"]["hypothesis_graph"]
    assert sd.REPORT.exists()


def test_a_certificate_without_params_cannot_be_stepped_and_says_so(ground):
    key, cert = _cert("TOYUSD", {}, key="qquant.hunt16.json.TOYUSD legacy cell")
    del cert["shadow_spec"]["params"]
    _write_canon(ground.canon, [(key, cert)])
    rep = sd.run(budget_s=5.0)
    assert rep["skipped"][f"canon:{key}"].startswith("certificate carries no exact params")


def test_symbols_filter_and_budget_are_honoured(ground):
    rep = sd.run(budget_s=60.0, symbols=["toyusd"])
    assert rep["certified_swept"] == 3            # 2 canon + the graph's own certified node
    rep = sd.run(budget_s=-1.0)
    assert rep["tests_run"] == 0
    assert any(v == "distiller budget exhausted" for v in rep["skipped"].values())


# ------------------------------------------------------------------------------------------
# 3. mutation yield
# ------------------------------------------------------------------------------------------

def _discovery(sym: str, params: dict, operator: str, parent: str, generator=None) -> dict:
    ev = {"parent": parent, "operator": operator, "t_gross": 3.0}
    if generator:
        ev["generator"] = generator
    return {"source": sd.SOURCE, "kind": sd.SOURCE, "symbol": sym, "family": FAM,
            "params": params, "mechanism": "toy (mutation: x)", "title": "t", "url": "",
            "evidence": ev, "available_time": "2026-08-26T00:00:00+00:00"}


def _write_discoveries(intel: Path, source: str, rows: list[dict]) -> None:
    d = intel / source
    d.mkdir(parents=True, exist_ok=True)
    (d / "discoveries_20260826_0000.json").write_text(json.dumps(
        {"source": source, "generated_at": "2026-08-26T00:00:00+00:00", "tests_run": len(rows),
         "discoveries": rows}), "utf-8")


def test_yield_joins_discoveries_to_verdicts_and_weights_operators(ground):
    root_key = ground.certs[0][0]
    p_up1 = {"feature": "x", "band": [0.75, 0.9], "horizon": 12, "side": 1}
    p_up2 = {"feature": "x", "band": [0.75, 1.0], "horizon": 6, "side": 1}
    p_dn1 = {"feature": "x", "band": [0.5, 0.9], "horizon": 6, "side": 1}
    p_dn2 = {"feature": "x", "band": [0.5, 0.75], "horizon": 6, "side": 1}
    p_grand = {"feature": "x", "band": [0.75, 1.0], "horizon": 24, "side": 1}
    child_key = f"graph:{node_id('TOYUSD', FAM, p_up2)}"
    _write_discoveries(my.INTEL, sd.SOURCE, [
        _discovery("TOYUSD", p_up1, "step_horizon_up", root_key),
        _discovery("TOYUSD", p_up2, "step_band_up", root_key, generator="gflow"),
        _discovery("TOYUSD", p_dn1, "step_band_down", root_key, generator="random"),
        _discovery("TOYUSD", p_dn2, "step_band_down", root_key),
        _discovery("TOYUSD", p_grand, "step_horizon_up", child_key),      # a child of a child
    ])
    g = ground.graph
    for params, fate, hours in ((p_up1, "CERTIFIED", 5), (p_up2, "CERTIFIED", 30),
                                (p_dn1, "FAILED", 10), (p_dn2, "FAILED", 2)):
        g.append(Node("TOYUSD", FAM, params, source="miner:survivor_distiller", fate="BORN",
                      at="2026-08-26T00:00:00+00:00"))
        g.append(Node("TOYUSD", FAM, params, source="gauntlet", fate=fate,
                      at=f"2026-08-26T{hours % 24:02d}:00:00+00:00"
                      if hours < 24 else "2026-08-27T06:00:00+00:00"))
    rep = my.run()
    ops = rep["by_operator"]
    assert ops["step_horizon_up"]["trials"] == 2
    assert ops["step_horizon_up"]["certified"] == 1 and ops["step_horizon_up"]["pending"] == 1
    assert ops["step_band_down"] == {**ops["step_band_down"], "trials": 2, "failed": 2,
                                     "certified": 0}
    assert ops["step_band_up"]["posterior"]["mean"] == pytest.approx(2 / 3, abs=1e-3)
    assert ops["step_band_down"]["posterior"]["mean"] == pytest.approx(1 / 4, abs=1e-3)
    # lineage depth: the grandchild's chain runs root -> child -> grandchild
    assert ops["step_horizon_up"]["depth"]["max"] == 2
    assert ops["step_band_up"]["depth"]["max"] == 1
    # time to verdict from BORN to the first verdict row
    assert ops["step_horizon_up"]["time_to_verdict_h"] == {"n": 1, "median": 5.0, "max": 5.0}
    assert ops["step_band_down"]["time_to_verdict_h"]["median"] == 6.0
    # per source, the graph's "miner:" prefix is stripped
    assert rep["by_source"][sd.SOURCE]["trials"] == 5
    assert rep["by_source"][sd.SOURCE]["certified"] == 2
    # weights: posterior mean / pooled mean, clipped
    w = json.loads(my.OPERATOR_WEIGHTS.read_text())
    pooled = (1 + 2) / (2 + 2 + 2)
    assert w["step_band_up"] == pytest.approx(min(4.0, (2 / 3) / pooled), abs=1e-3)
    assert w["step_band_down"] == pytest.approx(max(0.25, 0.25 / pooled), abs=1e-3)
    assert min(v for k, v in w.items() if not k.startswith("_")) >= 0.25
    assert max(v for k, v in w.items() if not k.startswith("_")) <= 4.0
    assert "_reason" in w and w["_pooled_mean"] == pytest.approx(pooled)
    # generators: gflow certified, random failed, symreg never seen -> 1.0 with the reason
    gw = json.loads(my.GENERATOR_WEIGHTS.read_text())
    assert gw["gflow"] > 1.0 > gw["random"] and gw["symreg"] == 1.0
    assert "2 groups" in gw["_reason"]
    assert my.REPORT.exists()


def test_yield_writes_uniform_weights_with_the_reason_when_nothing_is_seen(ground):
    rep = my.run()
    assert rep["n_lineage_rows"] == 0
    w = json.loads(my.OPERATOR_WEIGHTS.read_text())
    assert [k for k in w if not k.startswith("_")] == []
    assert "every weight at 1.0" in w["_reason"]
    gw = json.loads(my.GENERATOR_WEIGHTS.read_text())
    assert {k: v for k, v in gw.items() if not k.startswith("_")} == dict.fromkeys(
        my.GENERATORS, 1.0)
    assert "every weight at 1.0" in gw["_reason"]
    assert rep["inputs"]["discoveries"].startswith("no intelligence dir")
    # and the distiller reads that file as "uniform", not as a crash
    sd_w, note = sd._weights()
    assert sd_w == {} and "0 operator weights" in note


def test_yield_clips_at_both_ends(ground):
    """Six certificates under one operator against thirty failures under another: the raw
    ratios are ~4.8 and ~0.17, and the file must hold 4.0 and 0.25."""
    rows, winners, losers = [], [], []
    for i in range(6):
        p = {"feature": "x", "band": [0.75, 0.9], "horizon": 100 + i, "side": 1}
        winners.append(p)
        rows.append(_discovery("TOYUSD", p, "step_horizon_up", ground.certs[0][0]))
    for i in range(30):
        p = {"feature": "x", "band": [0.01 * i, 0.5], "horizon": 3, "side": -1}
        losers.append(p)
        rows.append(_discovery("TOYUSD", p, "swap_side", ground.certs[0][0]))
    _write_discoveries(my.INTEL, sd.SOURCE, rows)
    for p in winners:
        ground.graph.append(Node("TOYUSD", FAM, p, source="gauntlet", fate="CERTIFIED"))
    for p in losers:
        ground.graph.append(Node("TOYUSD", FAM, p, source="gauntlet", fate="FAILED"))
    rep = my.run()
    w = rep["operator_weights"]["weights"]
    pooled = (1 + 6) / (2 + 6 + 30)
    assert rep["operator_weights"]["pooled_mean"] == pytest.approx(pooled, abs=1e-3)
    assert (7 / 8) / pooled > 4.0 and (1 / 32) / pooled < 0.25      # the raw ratios
    assert w["step_horizon_up"] == 4.0
    assert w["swap_side"] == 0.25


# ------------------------------------------------------------------------------------------
# 4. the typed memory
# ------------------------------------------------------------------------------------------

@pytest.fixture
def memdir(tmp_path, monkeypatch):
    d = tmp_path / "memory"
    monkeypatch.setattr(mem, "MEMORY_DIR", d)
    return d


def test_remember_dedupes_exact_key_and_text(memdir):
    a = mem.remember("fact", "k1", "the desk trades the MT5 universe", source="t")
    b = mem.remember("fact", "k1", "the desk trades   the MT5 universe", source="t")
    c = mem.remember("fact", "k1", "a different sentence", source="t")
    assert a["new"] and not b["new"] and c["new"]
    assert a["id"] == b["id"] != c["id"]
    assert mem.digest("fact")["n"] == 2
    assert (memdir / "fact.jsonl").exists()
    with pytest.raises(ValueError):
        mem.remember("rumour", "k", "x", source="t")


def test_recall_ranks_by_overlap_and_skips_superseded(memdir):
    mem.remember("failure", "r1", "EURCHF discovered drawdown horizon 12 failed stress costs",
                 source="t")
    old = mem.remember("failure", "r2", "XAUUSD session range breakout failed lockbox", source="t")
    mem.remember("failure", "r2", "XAUUSD session range breakout later CERTIFIED after re-test",
                 source="t", supersedes=old["id"])
    mem.remember("method", "OP-001", "GitHub dig chain repo readme issues forks", source="t")
    got = mem.recall("failure", "EURCHF drawdown horizon 12")
    assert got and got[0]["key"] == "r1" and got[0]["score"] > 0
    assert all(g["id"] != old["id"] for g in mem.recall(None, "XAUUSD session breakout"))
    assert [g["key"] for g in mem.recall(None, "XAUUSD session breakout")] == ["r2"]
    assert mem.recall("failure", "") == []
    assert mem.recall("failure", "nothing shared here at all") == []
    everything = mem.recall(None, "GitHub forks EURCHF", k=1)
    assert len(everything) == 1


def test_cjk_text_is_searchable_by_bigrams(memdir):
    mem.remember("method", "OP-002", "native query 量化交易 数据 免费 templates", source="t")
    mem.remember("method", "OP-003", "comment layer mining", source="t")
    assert mem.tokenize("量化交易") == {"量化", "化交", "交易"}
    assert "免" in mem.tokenize("免 x")            # a lone CJK char stays searchable
    got = mem.recall("method", "交易数据")
    assert got and got[0]["key"] == "OP-002"


def test_digest_reports_counts_newest_and_sources(memdir):
    assert mem.digest("regime") == {"kind": "regime", "n": 0, "n_active": 0, "newest": None,
                                    "top_sources": [], "path": str(memdir / "regime.jsonl")}
    mem.remember("regime", "g1", "gap one", source="regime_coverage")
    mem.remember("regime", "g2", "gap two", source="regime_coverage")
    mem.remember("regime", "g3", "gap three", source="other")
    d = mem.digest("regime")
    assert d["n"] == 3 and d["top_sources"][0] == ("regime_coverage", 2)
    assert d["newest"]["key"] == "g3"


def _synthetic_root(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    data = root / "desks" / "mt5" / "data"
    data.mkdir(parents=True)
    g = Graph(data / "hypothesis_graph.jsonl")
    # Three distinct nodes in ONE region: `lookback` is bucketed 100 wide, so 100/110/120 share
    # the bucket [100,200) and the memory aggregates them as one corpse with a count of 3.
    for i in range(3):
        g.append(Node("EURCHF", "discovered", {"feature": "dd_12", "band": [0.0, 0.1],
                                               "horizon": 12, "side": 1, "lookback": 100 + 10 * i},
                      source="external", fate="FAILED", why="canonical verdict REJECTED"))
    g.append(Node("XAUUSD", "session_range_breakout", {"rr": 2.0, "wait_bars": 12},
                  source="external", fate="CERTIFIED", why="canonical verdict PASSED"))
    _write_canon(data / "UNIVERSAL_SURVIVORS.canon.json",
                 [_cert("USDJPY", {"rr": 1.5, "wait_bars": 12})])
    reports = root / "desks" / "mt5" / "reports"
    reports.mkdir()
    (reports / "REGIME_COVERAGE.json").write_text(json.dumps(
        {"gaps": {"weekday": "no sleeve covers Monday"},
         "uncovered": ["global=bull/high_vol|event=NORMAL|weekday=Mon"]}))
    (reports / "NETTING.json").write_text(json.dumps({"n_pairs": 4, "verdict": "NET"}))
    docs = root / "docs" / "research"
    docs.mkdir(parents=True)
    (root / "docs" / "graveyard.md").write_text(
        "# Graveyard\n\n## kimchi_style_calendar_effect -- daily close-to-close (KILLED)\n"
        "Body of the kill: the effect is a marking artifact.\n\n"
        "### gotobi_drift -- replicated then measured dead\nnothing survives costs\n")
    (docs / "search_operator_library.md").write_text(
        "## Entry schema\n```\n### OP-<nnn> name\n```\n\n### OP-001 GitHub-maximal dig chain"
        "   [active]\nclass: repo-discovery\ntechnique: repo -> README -> issues\n\n"
        "### OP-002 Native-language query templates   [active]\ntechnique: 量化交易 数据\n")
    (root / "docs" / "GROWTH_GOVERNANCE.md").write_text(
        "# Growth governance\n\n> **Rule 1.** Every risk reduction mechanism must prove that it "
        "increases robust forward E[log W].\n\n> **Rule 2.** Every strong opportunity must be "
        "allowed to increase capital above normal.\n\n## The heat law\n\n* The utilisation floor "
        "is **20% (HEAT_TARGET), flat, 24/7**. It does not ramp with readiness.\n* short\n")
    return root


def test_build_from_artifacts_is_idempotent_and_names_absent_inputs(tmp_path, memdir):
    root = _synthetic_root(tmp_path)
    first = mem.build_from_artifacts(root)
    assert first["added"]["failure"] == 1 + 2             # one graph region + 2 graveyard headings
    assert first["added"]["survivor"] == 1 + 1              # graph CERTIFIED + canon
    assert first["added"]["regime"] == 2
    assert first["added"]["execution"] == 1                 # NETTING present, FILL_SURFACE absent
    assert first["added"]["method"] == 2
    assert first["added"]["fact"] == 3                      # two rules + one long bullet
    assert first["inputs"]["fill_surface"] == "absent or unreadable"
    assert first["inputs"]["hypothesis_graph"] == "1 buried regions, 1 certified nodes"
    second = mem.build_from_artifacts(root)
    assert all(n == 0 for n in second["added"].values())
    assert second["seen"] == first["seen"]
    # the buried region carries its count and the last why
    got = mem.recall("failure", "EURCHF discovered dd_12")[0]
    assert "FAILED 3x" in got["text"] and "canonical verdict REJECTED" in got["text"]
    assert got["evidence"]["n_failed"] == 3
    assert mem.recall("method", "交易")[0]["key"] == "OP-002"
    assert mem.recall("fact", "risk reduction E[log W]")[0]["key"] == "growth_governance:rule_1"
    empty = mem.build_from_artifacts(tmp_path / "nowhere")
    assert all(n == 0 for n in empty["added"].values())
    assert empty["inputs"]["hypothesis_graph"] == "absent"
    assert empty["inputs"]["graveyard_md"] == "absent"


def test_prompt_context_surfaces_the_corpse_for_a_deepening_task(tmp_path, memdir):
    mem.build_from_artifacts(_synthetic_root(tmp_path))
    task = {"source": "world_crawler", "kind": None, "family": "discovered",
            "symbols": ["EURCHF"], "title": "EURCHF drawdown fade dd_12 horizon 12",
            "description": "a forum post claims fading 12-bar drawdown on EURCHF pays"}
    ctx = mem.prompt_context(task)
    assert ctx.startswith("[failure] discovered on EURCHF")
    assert "FAILED 3x" in ctx
    assert all(line.startswith("[") for line in ctx.splitlines())
    tight = mem.prompt_context(task, limit_chars=120)
    assert len(tight) <= 120 and tight.count("\n") == 0
    assert mem.prompt_context({}) == ""
    assert mem.prompt_context({"title": "zzzz qqqq"}) == ""
