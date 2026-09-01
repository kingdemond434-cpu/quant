"""The resolve_inputs memo must be invisible: same answer, fewer rebuilds.

A cache on the cross-asset universe is only safe if a cached call is INDISTINGUISHABLE from a
fresh one. If it is not, every `discovered` cell built from a hit is judged on a different
feature set than the one its identity claims, and the gate verdicts are quietly wrong -- the
same shape as the day-state lookahead defect (180 survivors -> 9, zero overlap).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import edge_search  # noqa: E402


@pytest.fixture
def synthetic(monkeypatch):
    """Deterministic closes so a rebuild and a hit are comparable bit for bit."""
    idx = pd.date_range("2024-01-01", periods=400, freq="h", tz="UTC")

    def _close(sym: str):
        seed = abs(hash(sym)) % 9973
        rng = np.random.default_rng(seed)
        return pd.Series(100.0 + np.cumsum(rng.normal(0, 0.1, len(idx))), index=idx)

    monkeypatch.setattr(edge_search, "_close", _close)
    edge_search._RESOLVE_CACHE.clear()
    return idx


def _same(a: dict, b: dict) -> bool:
    if set(a) != set(b):
        return False
    for k in a:
        x, y = a[k], b[k]
        if isinstance(x, pd.Series) and isinstance(y, pd.Series):
            if not x.equals(y):
                return False
        elif not (x is y or x == y):
            return False
    return True


def test_cached_call_is_bit_identical_to_a_fresh_one(synthetic):
    idx = synthetic
    peers = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    fresh = edge_search.resolve_inputs("XAUUSD", idx, peers)
    assert len(edge_search._RESOLVE_CACHE) == 1
    hit = edge_search.resolve_inputs("XAUUSD", idx, peers)
    assert _same(fresh, hit), "a cache hit returned a different universe than the rebuild"
    assert fresh, "guard: the fixture must actually produce primitives, or this proves nothing"


def test_a_caller_mutating_the_result_cannot_corrupt_the_next_cell(synthetic):
    idx = synthetic
    peers = ["EURUSD", "GBPUSD"]
    first = edge_search.resolve_inputs("XAUUSD", idx, peers)
    keys_before = set(first)
    first["INJECTED"] = "poison"
    first.pop(next(iter(keys_before)), None)
    second = edge_search.resolve_inputs("XAUUSD", idx, peers)
    assert "INJECTED" not in second
    assert set(second) == keys_before


def test_a_different_symbol_is_a_different_entry(synthetic):
    idx = synthetic
    peers = ["EURUSD", "GBPUSD"]
    a = edge_search.resolve_inputs("XAUUSD", idx, peers)
    b = edge_search.resolve_inputs("EURUSD", idx, peers)
    assert not _same(a, b), "two symbols must not share one universe"


def test_depth_is_bounded_so_the_box_cannot_be_exhausted(synthetic):
    idx = synthetic
    peers = ["EURUSD", "GBPUSD"]
    for sym in ("XAUUSD", "EURUSD", "USDJPY", "AUDUSD", "GBPUSD"):
        edge_search.resolve_inputs(sym, idx, peers)
    assert len(edge_search._RESOLVE_CACHE) <= edge_search._RESOLVE_CACHE_DEPTH


def test_eviction_still_returns_a_correct_universe(synthetic):
    """Depth 2 only pays off on symbol-ordered input; an evicted symbol must still be RIGHT."""
    idx = synthetic
    peers = ["EURUSD", "GBPUSD"]
    first = edge_search.resolve_inputs("XAUUSD", idx, peers)
    for sym in ("EURUSD", "USDJPY", "AUDUSD"):      # push XAUUSD out
        edge_search.resolve_inputs(sym, idx, peers)
    rebuilt = edge_search.resolve_inputs("XAUUSD", idx, peers)
    assert _same(first, rebuilt), "a rebuild after eviction diverged from the original"


def test_key_separates_different_bar_sets(synthetic):
    idx = synthetic
    peers = ["EURUSD", "GBPUSD"]
    k_full = edge_search._resolve_cache_key("XAUUSD", idx, peers)
    k_short = edge_search._resolve_cache_key("XAUUSD", idx[:-1], peers)
    k_peers = edge_search._resolve_cache_key("XAUUSD", idx, [*peers, "NZDUSD"])
    assert k_full != k_short, "a different bar count must not read a stale universe"
    assert k_full != k_peers, "adding a peer changes every residual and must miss"
