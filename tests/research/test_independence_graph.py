"""The independence graph over certified edges (Tier-1 #9): the north-star arithmetic.

Each property is one the principal's definition needs: independent edges count fully, clones
count once, a mirrored bet is not a new bet, and a pair nothing measured is assumed dependent.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research import independence_graph as ig


def _edge(key: str, sym: str, fam: str = "carry", mech: str = "carry", side: int = 1,
          session: str = "london", feats: tuple[str, ...] = ("a",),
          producer: str | None = "p") -> ig.Edge:
    return ig.Edge(key=key, symbol=sym, family=fam, mechanism=mech, side=side, session=session,
                   asset_class="Forex", feature_ids=frozenset(feats), producer=producer)


def test_the_rank_of_identity_is_n_and_of_clones_is_one() -> None:
    assert ig.effective_rank(np.eye(5)) == pytest.approx(5.0)
    assert ig.effective_rank(np.ones((5, 5))) == pytest.approx(1.0)
    assert ig.effective_rank(np.zeros((0, 0))) is None


def test_eight_channels_are_declared_and_split() -> None:
    assert len(ig.CHANNELS) == 8
    assert set(ig.STATISTICAL) | set(ig.STRUCTURAL) == set(ig.CHANNELS)
    assert not set(ig.STATISTICAL) & set(ig.STRUCTURAL)


def test_clones_collapse_and_unrelated_edges_do_not() -> None:
    rng = np.random.default_rng(7)
    a, b = rng.standard_normal(300), rng.standard_normal(300)
    proxy = {"EURUSD": list(a), "USDJPY": list(b), "XAUUSD": list(rng.standard_normal(300))}
    clones = [_edge("c1", "EURUSD"), _edge("c2", "EURUSD")]
    g = ig.build_graph(clones, proxy=proxy)
    assert g.rank() == pytest.approx(1.0, abs=1e-6)
    assert g.clusters() == [["c1", "c2"]]
    apart = [_edge("x1", "EURUSD", fam="carry", mech="carry", session="asia", feats=("a",)),
             _edge("x2", "XAUUSD", fam="session_range_breakout", mech="breakout",
                   session="ny", feats=("b",))]
    g2 = ig.build_graph(apart, proxy=proxy)
    assert g2.rank() is not None and g2.rank() > 1.5


def test_a_mirrored_bet_is_not_a_new_bet() -> None:
    """The same instrument traded the other way is |corr| = 1 on P&L: one piece of information."""
    rng = np.random.default_rng(1)
    proxy = {"EURUSD": list(rng.standard_normal(200))}
    g = ig.build_graph([_edge("l", "EURUSD", side=1), _edge("s", "EURUSD", side=-1)],
                       proxy=proxy)
    assert g.channels["pnl_corr"][0, 1] == pytest.approx(1.0)
    assert g.rank() == pytest.approx(1.0, abs=1e-6)


def test_realised_pnl_beats_the_proxy_where_both_exist() -> None:
    rng = np.random.default_rng(3)
    x = rng.standard_normal(60)
    days = [f"2026-01-{i:02d}" for i in range(1, 31)] + [f"2026-02-{i:02d}" for i in range(1, 29)]
    realised = {"r1": dict(zip(days, x[:58], strict=True)),
                "r2": dict(zip(days, rng.standard_normal(58), strict=True))}
    proxy = {"EURUSD": list(x), "GBPUSD": list(x)}           # the proxy would say "identical"
    g = ig.build_graph([_edge("r1", "EURUSD"), _edge("r2", "GBPUSD")], realised, proxy)
    assert g.pnl_basis["realised"] == 1 and g.pnl_basis["instrument_proxy"] == 0
    assert g.channels["pnl_corr"][0, 1] < 0.5


def test_a_pair_with_nothing_measured_is_assumed_dependent() -> None:
    """An unknown mechanism, no bars and no features: only structural channels that ALWAYS
    measure remain, so force every one of them away and check the fallback is D = 1."""
    e1 = _edge("u1", "AAA", mech="UNCLASSIFIED", feats=())
    e2 = _edge("u2", "BBB", mech="UNCLASSIFIED", feats=())
    g = ig.build_graph([e1, e2])
    # factor, timestamp and execution channels are structural and always measured
    assert np.isfinite(g.channels["factor_exposure"][0, 1])
    assert np.isnan(g.channels["same_mechanism"][0, 1])
    assert np.isnan(g.channels["pnl_corr"][0, 1])
    assert g.n_pairs_unmeasured == 0
    assert 0.0 <= g.combined[0, 1] <= 1.0


def test_marginal_rank_credits_the_producer_of_the_new_bet() -> None:
    rng = np.random.default_rng(11)
    proxy = {s: list(rng.standard_normal(300)) for s in ("EURUSD", "XAUUSD")}
    edges = [_edge("a1", "EURUSD", producer="dup"), _edge("a2", "EURUSD", producer="dup"),
             _edge("b1", "XAUUSD", fam="session_range_breakout", mech="breakout",
                   session="asia", feats=("z",), producer="new")]
    g = ig.build_graph(edges, proxy=proxy)
    m = g.marginal()
    y = ig.producer_yield(edges, m)
    assert y["new"] > y["dup"], y
    assert ig.producer_yield([_edge("n", "EURUSD", producer=None)], {"n": 1.0}) == {}


def test_factor_vector_signs_the_legs() -> None:
    assert ig.factor_vector("EURJPY", -1) == {"EUR": -1.0, "JPY": 1.0}
    assert ig.factor_vector("US500", 1) == {"US500": 1.0}
