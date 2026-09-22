"""The expression factory's DSL: typing and units (a mismatch is a compile error), the operator
catalogue with its macros, dimension-preserving mutations, the compiled evaluator's cache, the
canonical form and trial family, and the 101 parent genomes' census."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from libs.research import alpha_dsl as dsl
from libs.research import alpha_grammar as ag

N = 3000


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.Series]:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2024-01-01", periods=N, freq="1h", tz="UTC")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.001, N))), index=idx)
    bars = pd.DataFrame({"open": close.shift(1).bfill(), "high": close * 1.001,
                         "low": close * 0.999, "close": close,
                         "tick_volume": 100 + rng.integers(0, 50, N), "spread": 10.0}, index=idx)
    return ag.terminal_frames(bars, raw=bars)


# ------------------------------------------------------------------ typing and units
def test_every_node_is_typed_in_the_seven_word_vocabulary() -> None:
    c = dsl.compile_expr(["zscore", ["sub", ["mean", "close", 5], ["mean", "close", 24]], 240])
    kinds = {n.kind for n in c.dag.values()}
    assert kinds <= set(dsl.DSL_TYPES)
    assert c.kind == "ratio" and c.dtype == "Z" and c.unit == "1"
    by_op = {n.op: n for n in c.dag.values()}
    assert by_op["close"].kind == "price" and by_op["close"].unit == "quote^1"
    assert by_op["window"].kind == "time" and by_op["window"].unit == "bars^1"
    assert dsl.kind_of("ret") == "return" and dsl.kind_of("activity") == "volume"
    assert dsl.kind_of(["bars_since_max", "close", 24]) == "time"
    assert dsl.kind_of(["delta", "close", 5]) == "price"
    assert dsl.kind_of(["gt", "close", "open"]) == "bool"


def test_a_shared_subtree_is_one_dag_node() -> None:
    sub = ["mean", "close", 24]
    c = dsl.compile_expr(["div", ["sub", "close", sub], sub])
    assert sum(1 for n in c.dag.values() if n.op == "mean") == 1
    assert c.n_nodes == 5   # close, window 24, mean, sub, div


@pytest.mark.parametrize("bad", [
    ["add", "close", "activity"],                          # a price plus a tick count
    ["add", ["std", "close", 24], ["std", "ret", 24]],     # a price dispersion plus a pure number
    ["gt", "close", "activity"],                           # a logic macro over unlike units
    ["sub", "spread", "close"],                            # pips minus quote
])
def test_a_unit_mismatch_is_a_compile_error_not_a_nan(bad: list[Any]) -> None:
    with pytest.raises(dsl.UnitMismatch) as exc:
        dsl.compile_expr(bad)
    assert "mismatch" in str(exc.value)


def test_structural_defects_are_compile_errors_too() -> None:
    with pytest.raises(dsl.CompileError):
        dsl.compile_expr(["mean", "close", 7])              # 7 is not a grammar window
    with pytest.raises(dsl.CompileError):
        dsl.compile_expr(["frobnicate", "close"])
    with pytest.raises(dsl.CompileError):
        dsl.compile_expr(["mean", "positioning", 24], terminals=("close", "ret"))


# ------------------------------------------------------------------ the operator catalogue
def test_catalogue_covers_every_grammar_operator_and_the_seven_categories() -> None:
    cat = dsl.OPERATOR_CATALOGUE
    assert set(ag.ALL_OPERATORS) <= set(cat)
    census = dsl.catalogue_census()
    assert set(census["by_category"]) == set(dsl.OP_CATEGORIES)
    assert all(census["by_category"][c] for c in dsl.OP_CATEGORIES)
    assert cat["ts_rank"].category == "time_series" and cat["xrank"].category == "cross_sectional"
    assert cat["group_zscore"].category == "group" and cat["trade_when"].category == "logic"
    assert cat["event_decay"].category == "event" and cat["when_regime"].category == "regime"
    for spec in cat.values():
        assert spec.signature and spec.category in dsl.OP_CATEGORIES


def test_macros_and_aliases_lower_into_valid_grammar_trees() -> None:
    assert dsl.lower(["ts_argmax", "close", 24]) == ["bars_since_max", "close", 24]
    assert dsl.lower(["ts_mean", "close", 24]) == ["mean", "close", 24]
    assert dsl.lower(["not", "ret"]) == ["neg", ["sign", "ret"]]
    for e in (["and", "ret", "body"], ["or", ["gt", "close", "open"], "ret"],
              ["when_regime", ["delta", "close", 5]], ["regime_neutral", "ret", 24],
              ["event_gate", "ret"], ["bars_since_event", 48]):
        low = dsl.lower(e)
        assert ag.is_valid(low, terminals=ag.TERMINALS), e
        assert not (dsl.operators_in(low) & set(dsl.OPERATOR_CATALOGUE) - set(ag.ALL_OPERATORS))
    assert dsl.kind_of(["and", "ret", "body"]) == "bool"


# ------------------------------------------------------------------ the mutation engine
def test_every_move_is_dimension_preserving_or_returns_none() -> None:
    rng = np.random.default_rng(3)
    produced = dict.fromkeys(dsl.MUTATIONS, 0)
    for _ in range(150):
        parent = ag.random_expr(rng, 3)
        partner = ag.random_expr(rng, 3)
        for move in dsl.MUTATIONS:
            child = dsl.mutate(parent, move, rng, partner=partner)
            if child is None:
                continue
            produced[move] += 1
            assert ag.is_valid(child), (move, parent, child)
            assert ag.unit_of(child) == ag.unit_of(parent), (move, parent, child)
            assert ag.key(child) != ag.key(parent)
    assert all(produced[m] > 0 for m in dsl.MUTATIONS), produced


def test_constant_perturbation_changes_only_a_window_and_simplify_is_exact() -> None:
    rng = np.random.default_rng(1)
    parent = ["zscore", ["sub", ["mean", "close", 5], ["mean", "close", 24]], 240]
    child = dsl.mutate(parent, "constant", rng)
    assert child is not None
    assert dsl.skeleton(child) == dsl.skeleton(parent)
    assert dsl.windows_in(child) != dsl.windows_in(parent)
    assert dsl.mutate(parent, "simplify", rng) is None            # already canonical
    assert dsl.mutate(["neg", ["neg", "ret"]], "simplify", rng) == "ret"
    assert dsl.mutate(parent, "crossover", rng, partner=None) is None
    with pytest.raises(ValueError):
        dsl.mutate(parent, "teleport", rng)


def test_point_mutation_swaps_a_leaf_for_one_of_the_same_kind() -> None:
    rng = np.random.default_rng(2)
    parent = ["delta", "close", 24]
    for _ in range(20):
        child = dsl.mutate(parent, "point", rng, terminals=ag.BAR_TERMINALS)
        assert child is not None and child[0] == "delta" and child[2] == 24
        assert ag.TERMINAL_KINDS[child[1]] == ag.TERMINAL_KINDS["close"]


# ------------------------------------------------------------------ compiled evaluation + cache
def test_compiled_evaluation_matches_the_grammar_and_the_cache_hits(
        frames: dict[str, pd.Series]) -> None:
    c = dsl.compile_expr(["zscore", ["sub", ["mean", "close", 5], ["mean", "close", 24]], 240])
    cache = ag.SubtreeCache(max_entries=64, max_cells=10_000_000)
    scope = cache.scope("X", frames)
    first = c.evaluate(frames, scope)
    second = c.evaluate(frames, scope)
    plain = ag.evaluate(c.expr, frames, {})
    assert c.hits == 1 and c.misses == 1
    assert np.allclose(first.to_numpy(), plain.to_numpy(), equal_nan=True)
    assert np.allclose(second.to_numpy(), plain.to_numpy(), equal_nan=True)
    assert cache.stats()["hits"] >= 1
    # a different window is a different recipe: the cache must not serve the old series
    other = dsl.compile_expr(["zscore", ["sub", ["mean", "close", 8], ["mean", "close", 24]], 240])
    third = other.evaluate(frames, scope)
    assert not np.allclose(third.fillna(0).to_numpy(), first.fillna(0).to_numpy())


def test_canonical_form_and_trial_family_blank_the_windows() -> None:
    a = ["add", ["mean", "close", 12], ["mean", "close", 48]]
    b = ["add", ["mean", "close", 24], ["mean", "close", 8]]
    assert dsl.family_key(a) == dsl.family_key(b)
    assert dsl.canonical_key(["add", "ret", "body"]) == dsl.canonical_key(["add", "body", "ret"])
    assert dsl.canonical_key(a) != dsl.canonical_key(b)
    assert dsl.compile_expr(a).family == dsl.compile_expr(b).family


def test_the_101_parent_genomes_are_all_transcribed_and_partitioned() -> None:
    census = dsl.genome_census()
    assert census["n_parents"] == 101
    assert sum(census["by_status"].values()) == 101
    assert census["by_status"]["TESTABLE"] >= 20 and census["by_status"]["TOO_DEEP"] >= 5
    for aid, g in dsl.parent_genomes().items():
        assert g.formula and aid == g.alpha_id
        if g.status == "TESTABLE":
            assert g.tree is not None and ag.is_valid(g.tree), aid
