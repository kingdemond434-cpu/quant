"""Alpha DNA, strategy similarity, embedding/clustering, and feature drift."""

from __future__ import annotations

import numpy as np
from tests.alpha_factory.conftest import make_dna

from libs.alpha_factory.alpha_dna import build_alpha_dna, dna_distance
from libs.alpha_factory.alpha_embedding_engine import AlphaEmbeddingEngine
from libs.alpha_factory.strategy_similarity_engine import StrategySimilarityEngine
from libs.self_improvement.drift_detector import AlphaDriftDetector


def test_build_dna_and_distance() -> None:
    a = build_alpha_dna(signal_type="trend", market="XAUUSD", timeframe="H1",
                        holding_period="swing", trend_sensitivity=0.9)
    b = build_alpha_dna(signal_type="trend", market="XAUUSD", timeframe="H1",
                        holding_period="swing", trend_sensitivity=0.1)
    assert dna_distance(a, a) == 0.0
    assert dna_distance(a, b) > 0.0


def test_similarity_flags_duplicate() -> None:
    eng = StrategySimilarityEngine(duplicate_threshold=0.9)
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 200)
    dup = eng.similarity(
        returns_a=base, returns_b=base,
        factors_a={"momentum": 1.0}, factors_b={"momentum": 1.0},
        features_a=["x", "y"], features_b=["x", "y"],
    )
    assert dup.is_duplicate
    assert dup.return_similarity > 0.99

    distinct = eng.similarity(
        returns_a=base, returns_b=rng.normal(0, 1, 200),
        factors_a={"momentum": 1.0}, factors_b={"carry": 1.0},
        features_a=["x"], features_b=["z"],
    )
    assert not distinct.is_duplicate
    assert distinct.overall < dup.overall


def test_embedding_similarity_and_clustering() -> None:
    eng = AlphaEmbeddingEngine()
    a = make_dna(trend_sensitivity=0.9, factor_exposures={"momentum": 1.0})
    a_twin = make_dna(trend_sensitivity=0.9, factor_exposures={"momentum": 1.0})
    b = make_dna(trend_sensitivity=0.0, mean_reversion_sensitivity=0.9,
                 factor_exposures={"value": 1.0})
    assert eng.similarity(a, a_twin) > eng.similarity(a, b)
    clusters = eng.cluster({"a": a, "a_twin": a_twin, "b": b}, threshold=0.99)
    # the two near-identical alphas cluster together; b stands alone
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 2]


def test_similarity_handles_degenerate_inputs() -> None:
    eng = StrategySimilarityEngine()
    # empty returns / no factors / no features exercise every guard -> overall 0, not duplicate
    empty = eng.similarity(returns_a=[], returns_b=[])
    assert empty.overall == 0.0
    assert not empty.is_duplicate
    # constant (zero-variance) returns and mismatched lengths also yield zero similarity
    constant = eng.similarity(returns_a=[1.0, 1.0, 1.0], returns_b=[1.0])
    assert constant.return_similarity == 0.0
    # a zero-norm factor vector (present key, zero weight) yields zero cosine
    zero_factor = eng.similarity(
        returns_a=[1.0, 2.0, 3.0], returns_b=[1.0, 2.0, 3.0],
        factors_a={"momentum": 1.0}, factors_b={"momentum": 0.0},
    )
    assert zero_factor.factor_similarity == 0.0


def test_embedding_zero_vectors_have_zero_similarity() -> None:
    eng = AlphaEmbeddingEngine()
    zero = make_dna(
        factor_exposures={}, regime_affinity={}, volatility_sensitivity=0.0,
        trend_sensitivity=0.0, mean_reversion_sensitivity=0.0, turnover_profile=0.0,
        risk_profile=0.0,
    )
    other = make_dna()
    assert eng.similarity(zero, other) == 0.0


def test_feature_drift_detection() -> None:
    eng = AlphaDriftDetector(psi_threshold=0.2)
    rng = np.random.default_rng(1)
    stable = eng.detect(rng.normal(0, 1, 2000), rng.normal(0, 1, 2000))
    assert not stable.drifted
    shifted = eng.detect(rng.normal(0, 1, 2000), rng.normal(4, 1, 2000))
    assert shifted.drifted
    # AlphaDriftDetector says "trigger revalidation" where the retired FeatureDriftEngine
    # duplicate said "revalidate" -- same behaviour, one wording. Matching the stem keeps the
    # assertion about the RECOMMENDATION rather than about a phrase.
    assert "revalidat" in shifted.recommendation
