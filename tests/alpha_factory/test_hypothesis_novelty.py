"""Tests for the pre-compute hypothesis novelty gate (RD-Agent trace-conditioning)."""

from __future__ import annotations

from libs.alpha_factory.hypothesis_novelty import (
    NoveltyResult,
    PriorIdea,
    hypothesis_novelty,
)

_MOM = PriorIdea(
    id="i1",
    statement="momentum strengthens in low volatility regimes",
    features=("momentum", "volatility_regime"),
    lesson="failed DSR forward",
)


def test_exact_duplicate_is_redundant() -> None:
    r = hypothesis_novelty(
        "momentum strengthens in low volatility regimes",
        features=["momentum", "volatility_regime"],
        priors=[_MOM],
    )
    assert r.is_redundant
    assert r.novelty_score < 0.05
    assert r.nearest_id == "i1"
    assert r.nearest_lesson == "failed DSR forward"
    assert bool(r) is False  # redundant candidates are falsy (not worth testing)


def test_same_mechanism_different_wording_is_redundant() -> None:
    # identical feature set (same mechanism) but reworded statement -> still a re-test
    r = hypothesis_novelty(
        "low-vol names carry a momentum premium",
        features=["momentum", "volatility_regime"],
        priors=[_MOM],
    )
    assert r.is_redundant
    assert r.nearest_id == "i1"


def test_same_wording_different_mechanism_is_novel() -> None:
    # similar words but a genuinely different feature set (mechanism) -> novel, not blocked
    r = hypothesis_novelty(
        "momentum strengthens in low volatility regimes",
        features=["stablecoin_flow", "funding"],
        priors=[_MOM],
    )
    assert not r.is_redundant
    assert r.nearest_id == "i1"  # nearest is still surfaced for context


def test_genuinely_new_axis_is_maximally_flagged_novel() -> None:
    r = hypothesis_novelty(
        "stablecoin mint velocity predicts next-day perp funding",
        features=["stablecoin_flow", "funding"],
        priors=[_MOM],
    )
    assert not r.is_redundant
    assert r.novelty_score > 0.7


def test_no_priors_is_maximally_novel() -> None:
    r = hypothesis_novelty("anything at all", features=["x"], priors=[])
    assert r.novelty_score == 1.0
    assert r.nearest_id is None
    assert r.nearest_similarity == 0.0
    assert not r.is_redundant
    assert bool(r) is True


def test_statement_only_similarity_when_features_absent() -> None:
    prior = PriorIdea(id="i2", statement="cross sectional momentum predicts continuation")
    r = hypothesis_novelty(
        "cross sectional momentum predicts continuation", priors=[prior]
    )
    assert r.is_redundant  # identical statement, no features -> statement token match drives it
    assert r.nearest_id == "i2"


def test_returns_typed_result() -> None:
    r = hypothesis_novelty("x y z", features=["a"], priors=[_MOM])
    assert isinstance(r, NoveltyResult)
    assert 0.0 <= r.novelty_score <= 1.0
