"""Nine populations over one grammar: that each one proposes what it claims to, that the shared
subtree cache hits EXACTLY, and that the yield ledger counts what happened rather than what was
hoped for.

The three derived populations (graveyard, causal, claims) read ledgers other engines write, so
every one of them is exercised twice here: once against a tmp_path fixture with the schema, and
once against a path that does not exist -- because "the sibling has not written it yet" is the
normal state of this desk on any given hour and must produce a named zero, not an exception.

No network; every ledger path is a tmp_path.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_fitness as af
from libs.research import alpha_grammar as ag
from libs.research import search_populations as sp


def _bars(n: int = 900, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(1900 + np.cumsum(rng.normal(0, 0.6, n)), index=idx)
    return pd.DataFrame({"open": close.shift(1).bfill(), "high": close + 0.8,
                         "low": close - 0.8, "close": close,
                         "tick_volume": rng.integers(40, 800, n).astype(float),
                         "spread": rng.integers(8, 30, n).astype(float)}, index=idx)


def _ctx(tmp_path, *, seed: int = 0, drivers: bool = True, **kw) -> sp.SearchContext:
    df = _bars()
    drv = {"usd": _bars(len(df), seed=9)} if drivers else {}
    frames = ag.terminal_frames(df, raw=df, drivers=drv)
    rng = np.random.default_rng(seed)
    history = [(ag.random_expr(rng, 3), float(rng.normal())) for _ in range(24)]
    base = {"rng": rng, "frames": frames, "ret": frames["ret"], "symbol": "XAUUSD",
            "cache": ag.SubtreeCache(), "history": history,
            "seeds": list(ag.CANON.values()),
            "hypothesis_graph": tmp_path / "absent_graph.jsonl",
            "causal_graph": tmp_path / "absent_causal.json",
            "claims": tmp_path / "absent_claims.jsonl"}
    base.update(kw)
    return sp.SearchContext(**base)


# --------------------------------------------------------------------------- the registry
def test_the_registry_is_the_nine_declared_populations() -> None:
    assert set(sp.POPULATIONS) == {
        "gp", "gflownet", "symreg", "program_synthesis", "bayesian", "zoo_mutation",
        "graveyard_derived", "causal_derived", "claims_derived"}
    # the three-generator surface is UNCHANGED: populations are a separate registry, so the
    # generator weight table and everything reading it keeps meaning what it meant
    from libs.research import generators as gen
    assert list(gen.GENERATORS) == ["random", "gflow", "symreg"]


def test_every_population_only_ever_emits_trees_the_production_screen_accepts(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    for name, fn in sp.POPULATIONS.items():
        for e in fn(ctx, 6):
            assert ag.is_valid(e, ctx.allow_drivers, ctx.terminals), (name, ag.to_str(e))
            assert ag.well_formed(e), (name, ag.to_str(e))


def test_run_dedupes_across_populations_and_counts_what_happened(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    res = sp.run(ctx, n_per_population=5, budget_s=60)
    assert set(res.yields) == set(sp.POPULATIONS)
    hashes = [ag.subtree_hash(e) for e, _who in res.proposals]
    assert len(hashes) == len(set(hashes))                      # deduped ACROSS populations
    for name, y in res.yields.items():
        assert y.proposed >= y.unique >= y.well_formed >= y.passed, (name, y.as_dict())
        assert y.note, name
    assert res.yield_line()["populations"] == 9
    assert res.yield_line()["proposals"] == len(res.proposals)
    # a bare terminal is a level, not an alpha, and never reaches the proposals
    assert all(not isinstance(e, str) for e, _who in res.proposals)
    assert all(who in sp.POPULATIONS for _e, who in res.proposals)


def test_a_population_that_raises_costs_its_own_share_and_nothing_else(
        tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_ctx, _n):
        raise RuntimeError("the sampler fell over")
    monkeypatch.setitem(sp.POPULATIONS, "gflownet", boom)
    ctx = _ctx(tmp_path)
    res = sp.run(ctx, n_per_population=4, budget_s=60)
    assert res.yields["gflownet"].proposed == 0
    assert "RuntimeError" in res.yields["gflownet"].note
    assert any("gflownet" in f for f in res.failures)
    assert res.yields["gp"].proposed > 0                        # the sweep continued


def test_a_falsifier_is_applied_and_a_falsifier_that_raises_is_not_fatal(tmp_path) -> None:
    seen: list[str] = []

    def only_windowed(e) -> bool:
        seen.append(ag.to_str(e))
        return not isinstance(e, str) and str(e[0]) in ag.WINDOWED
    ctx = _ctx(tmp_path, falsifier=only_windowed)
    res = sp.run(ctx, n_per_population=4, budget_s=60)
    assert seen
    assert all(str(e[0]) in ag.WINDOWED for e, _who in res.proposals)
    assert any("cheap falsifier" in y.note for y in res.yields.values())

    def boom(_e) -> bool:
        raise ValueError("screen exploded")
    res2 = sp.run(_ctx(tmp_path, falsifier=boom), n_per_population=3, budget_s=60)
    assert not res2.proposals and res2.failures


def test_budget_exhaustion_skips_populations_rather_than_truncating_one(tmp_path) -> None:
    res = sp.run(_ctx(tmp_path), n_per_population=3, budget_s=-1.0)
    assert all(y.note == "budget exhausted before it ran" for y in res.yields.values())
    assert not res.proposals


def test_weights_reorder_but_never_starve_a_population(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    order = sp._order(None, {"zoo_mutation": 100.0, "gp": 1.0}, ctx.rng)
    assert set(order) == set(sp.POPULATIONS)                     # every arm still runs
    assert sp._order(None, {"nonsense": 1.0}, ctx.rng) == list(sp.POPULATIONS)
    assert sp._order(None, {"gp": float("nan")}, ctx.rng) == list(sp.POPULATIONS)
    assert sp._order(["gp", "symreg"], None, ctx.rng) == ["gp", "symreg"]
    assert sp._order(["not_a_population"], None, ctx.rng) == list(sp.POPULATIONS)


# --------------------------------------------------------------------------- the cache
def test_the_subtree_cache_hits_exactly_and_is_shared(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    cache = ctx.cache
    assert cache is not None
    shared = ["delta", "close", 24]
    a = ["zscore", shared, 240]
    b = ["ts_rank", shared, 48]
    first = ctx.evaluate(a)
    assert cache.stats()["hits"] == 0 and cache.stats()["entries"] == 3
    second = ctx.evaluate(b)
    # `delta(close, 24)` and `close` were paid for by `a`; `b` gets both free
    assert cache.stats()["hits"] == 1
    third = ctx.evaluate(a)
    assert cache.stats()["hits"] == 2
    assert third.equals(first) and not second.equals(first)
    # EXACT, not approximate: the cached series is the series the grammar computes uncached
    assert third.equals(ag.evaluate(a, ctx.frames))


def test_the_cache_key_separates_symbols_and_revised_bars(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    cache = ctx.cache
    expr = ["mean", "close", 12]
    ctx.evaluate(expr)
    hits = cache.stats()["hits"]
    other = cache.scope("EURUSD", ctx.frames)
    assert ag.evaluate(expr, ctx.frames, other) is not None
    assert cache.stats()["hits"] == hits                         # a different symbol: no hit
    revised = dict(ctx.frames)
    revised["close"] = ctx.frames["close"] + 1.0
    assert ag.frames_fingerprint("XAUUSD", revised) != ag.frames_fingerprint("XAUUSD", ctx.frames)
    ag.evaluate(expr, revised, cache.scope("XAUUSD", revised))
    assert cache.stats()["hits"] == hits                         # revised bars: no hit either
    assert ag.subtree_hash(expr) == ag.subtree_hash(["mean", "close", 12])
    assert ag.subtree_hash(expr) != ag.subtree_hash(["mean", "close", 24])


def test_the_cache_evicts_rather_than_growing_without_bound(tmp_path) -> None:
    ctx = _ctx(tmp_path, cache=ag.SubtreeCache(max_entries=3, max_cells=10_000_000))
    cache = ctx.cache
    assert cache is not None
    for w in (2, 3, 5, 8, 12, 24):
        ctx.evaluate(["mean", "close", w])
    assert cache.stats()["entries"] <= 3 and cache.stats()["evictions"] > 0
    tight = ag.SubtreeCache(max_entries=1000, max_cells=1)
    ag.evaluate(["mean", "close", 5], ctx.frames, tight.scope("X", ctx.frames))
    assert tight.stats()["entries"] <= 1


# --------------------------------------------------------------------------- gp / NSGA-II
def test_gp_breeds_from_the_pareto_front_and_falls_back_to_seeds(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    assert not ctx.scored
    assert len(gp_out := sp.gp(ctx, 5)) == 5                     # seeds only: still breeds
    assert all(ag.is_valid(e, ctx.allow_drivers) for e in gp_out)
    specialist = ["zscore", ["delta", "close", 120], 240]
    allrounder = ["ts_rank", "range", 48]
    dominated = ["mean", "activity", 24]
    ctx.scored = [(specialist, af.FitnessTerms(tail=9.0, cost=9.0)),
                  (allrounder, af.FitnessTerms(tail=1.0, cost=0.2)),
                  (dominated, af.FitnessTerms(tail=0.1, cost=5.0))]
    parents = sp._nsga_parents(ctx, keep=2)
    assert ag.key(dominated) not in {ag.key(p) for p in parents}
    assert len(sp.gp(ctx, 4)) == 4


def test_program_synthesis_enumerates_and_never_repeats_a_structure(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    out = sp.program_synthesis(ctx, 40)
    hashes = [ag.subtree_hash(e) for e in out]
    assert len(hashes) == len(set(hashes)) and len(out) > 10
    assert all(ag.depth(e) <= sp.SYNTH_MAX_DEPTH for e in out)
    # it does not re-derive what the history already tried
    known = ["mean", "close", 24]
    ctx.history = [*ctx.history, (known, 1.0)]
    again = sp.program_synthesis(ctx, 200)
    assert ag.key(known) not in {ag.key(e) for e in again}


def test_bayesian_prefers_the_features_the_history_rewarded(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    rng = np.random.default_rng(4)
    hot, cold = [], []
    while len(hot) < 20 or len(cold) < 20:
        e = ag.random_expr(rng, 3, allow_drivers=False)
        ops = sp.features(e)
        (hot if "op:zscore" in ops else cold).append(e)
    ctx.history = [(e, 3.0) for e in hot[:20]] + [(e, -3.0) for e in cold[:20]]
    picked = sp.bayesian(ctx, 20)
    rate = np.mean(["op:zscore" in sp.features(e) for e in picked])
    baseline = np.mean(["op:zscore" in sp.features(ag.random_expr(ctx.rng, 3))
                        for _ in range(300)])
    assert rate > baseline, (rate, baseline)
    assert sp.features(["zscore", "close", 24]) >= {"op:zscore", "t:close", "w:mid", "d:1"}
    # with no history it is a uniform draw, not a model fitted to nothing
    ctx.history = []
    assert len(sp.bayesian(ctx, 5)) == 5


# --------------------------------------------------------------------------- the alpha zoos
def test_every_zoo_template_is_a_typed_tree_of_this_grammar() -> None:
    for name, tpl in sp.ZOO_TEMPLATES.items():
        expr = tpl["expr"]
        assert ag.well_formed(expr), (name, ag.to_str(expr))
        assert tpl["family"] in ("alpha158", "wq101", "gtja191") and tpl["shape"]
    families = {t["family"] for t in sp.ZOO_TEMPLATES.values()}
    assert families == {"alpha158", "wq101", "gtja191"}


def test_the_zoo_is_never_proposed_as_written(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    published = {ag.key(t["expr"]) for t in sp.ZOO_TEMPLATES.values()}
    out = sp.zoo_mutation(ctx, 60)
    assert out
    assert not (published & {ag.key(e) for e in out}), "a zoo formula escaped unmutated"
    assert all(ag.is_valid(e, ctx.allow_drivers, ctx.terminals) for e in out)


def test_every_named_mutation_axis_changes_the_tree(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    base = ["zscore", "close", 24]
    for axis in sp.MUTATION_AXES:
        moved = sp._zoo_axis(base, axis, ctx)
        assert ag.key(moved) != ag.key(base), axis
        assert ag.well_formed(moved), (axis, ag.to_str(moved))
    assert sp.MUTATION_AXES == ("instrument", "horizon", "lag", "normalisation", "state",
                                "session", "cross_asset", "residualisation", "entry_exit")
    # the horizon axis snaps back onto the grammar's own window ladder
    rewound = sp._rewindow(["corr", "close", "activity", 24], ctx.rng, 4.0)
    assert rewound[-1] in ag.WINDOWS and rewound[-1] > 24


# --------------------------------------------------------------------------- derived ledgers
def test_graveyard_derived_uses_only_fates_that_NAME_a_cause(tmp_path) -> None:
    path = tmp_path / "graph.jsonl"
    path.write_text("\n".join([
        json.dumps({"fate": "FAILED", "why": "net of cost the edge is negative"}),
        json.dumps({"fate": "FAILED", "why": "unstable across halves"}),
        json.dumps({"fate": "FAILED", "why": "canonical verdict REJECTED"}),
        json.dumps({"fate": "CERTIFIED", "why": "cost"}),
        "{not json",
    ]) + "\n")
    axes, dead, named = sp._fates(path)
    assert dead == 3 and named == 2 and set(axes) == {"horizon"}
    ctx = _ctx(tmp_path, hypothesis_graph=path)
    out = sp.graveyard_derived(ctx, 6)
    assert out and all(ag.is_valid(e, ctx.allow_drivers, ctx.terminals) for e in out)
    assert "attackable cause" in ctx.notes["graveyard_derived"]


def test_graveyard_derived_says_so_when_no_fate_names_a_cause(tmp_path) -> None:
    path = tmp_path / "graph.jsonl"
    path.write_text(json.dumps({"fate": "FAILED", "why": "canonical verdict REJECTED"}) + "\n")
    ctx = _ctx(tmp_path, hypothesis_graph=path)
    assert sp.graveyard_derived(ctx, 5) == []
    assert "not genetic material" in ctx.notes["graveyard_derived"]
    absent = _ctx(tmp_path)
    assert sp.graveyard_derived(absent, 5) == []
    assert absent.notes["graveyard_derived"]


def test_causal_derived_uses_admitted_edges_only(tmp_path) -> None:
    path = tmp_path / "causal.json"
    path.write_text(json.dumps({"edges": [
        {"src": "fx:usd_index", "dst": "XAUUSD", "lag": 3, "status": "ADMITTED"},
        {"src": "fx:usd_index", "dst": "XAUUSD", "lag": 2, "status": "RECORDED_NOT_ADMITTED"},
        {"src": "unmappable:thing", "dst": "XAUUSD", "lag": 1, "status": "ADMITTED"},
        "not a dict",
    ]}))
    edges = sp._admitted_edges(path, ("usd",))
    assert edges == [("usd", 3)]
    ctx = _ctx(tmp_path, causal_graph=path)
    out = sp.causal_derived(ctx, 8)
    assert out and all(ag.is_valid(e, ctx.allow_drivers, ctx.terminals) for e in out)
    assert all("usd" in ag.terminals_in(e) for e in out)


def test_causal_derived_is_silent_and_named_when_the_graph_is_not_there(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    assert sp.causal_derived(ctx, 5) == []
    assert "no admitted edge" in ctx.notes["causal_derived"]
    broken = tmp_path / "broken.json"
    broken.write_text("[]")
    assert sp._admitted_edges(broken, ("usd",)) == []
    assert sp._admitted_edges(tmp_path / "nothing.json", ("usd",)) == []


def test_claims_derived_reads_one_draw_per_distinct_mechanism_key(tmp_path) -> None:
    path = tmp_path / "claims.jsonl"
    path.write_text("\n".join([
        json.dumps({"mechanism_class": "momentum", "mechanism_key": "m1", "channel": "direct"}),
        json.dumps({"mechanism_class": "momentum", "mechanism_key": "m1", "channel": "indirect"}),
        json.dumps({"mechanism_class": "flow", "mechanism_key": "m2"}),
        json.dumps({"mechanism_class": "unheard_of", "mechanism_key": "m3"}),
        json.dumps({"mechanism_class": "carry"}),                # no key: not counted
    ]) + "\n")
    classes = sp._claim_classes(path)
    assert classes == ["momentum", "flow"]                       # one per key, unknown dropped
    ctx = _ctx(tmp_path, claims=path)
    out = sp.claims_derived(ctx, 10)
    assert out and all(ag.is_valid(e, ctx.allow_drivers, ctx.terminals) for e in out)
    assert set(sp.CLAIM_SHAPES) <= {"momentum", "reversion", "flow", "microstructure",
                                    "positioning", "calendar", "inventory", "carry", "policy",
                                    "cross_asset"}


def test_claims_derived_is_silent_and_named_when_the_miner_has_not_written(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    assert sp.claims_derived(ctx, 5) == []
    assert "mechanism class" in ctx.notes["claims_derived"]
    assert sp._jsonl_tail(tmp_path / "nope.jsonl", 10) == []


# --------------------------------------------------------------------------- terminals
def test_the_context_only_lets_populations_draw_terminals_the_frames_carry(tmp_path) -> None:
    ctx = _ctx(tmp_path, drivers=False)
    assert "usd" not in ctx.terminals and ctx.drivers == ()
    assert set(ctx.terminals) <= set(ag.BAR_TERMINALS)
    for name, fn in sp.POPULATIONS.items():
        for e in fn(ctx, 4):
            assert not (ag.terminals_in(e) & set(ag.DRIVER_TERMINALS)), (name, ag.to_str(e))
    # an external terminal is never drawn just because the vocabulary declares it
    assert not (set(ctx.terminals) & set(ag.EXTERNAL_TERMINALS))
