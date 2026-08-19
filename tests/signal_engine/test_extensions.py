"""Signal embedding, market-impact forecast, alpha competition, and stress testing."""

from __future__ import annotations

import numpy as np
from tests.signal_engine.conftest import make_alpha, strong_obs

from libs.signal_engine.alpha_competition_engine import AlphaCompetitionEngine
from libs.signal_engine.engine import SignalEngine
from libs.signal_engine.models import Regime, TradeCandidate
from libs.signal_engine.signal_embedding_engine import SignalEmbeddingEngine, _cosine
from libs.signal_engine.stress_signal_engine import StressSignalEngine


def _candidate() -> TradeCandidate:
    built = SignalEngine()._build_candidate(strong_obs())
    assert isinstance(built, TradeCandidate)
    return built


def test_signal_embedding_similarity_and_clusters() -> None:
    eng = SignalEmbeddingEngine()
    a = _candidate()
    twin = _candidate()
    # same scores but a different regime -> the regime one-hot lowers cosine similarity
    other = a.model_copy(update={"regime": Regime.CRISIS})
    assert eng.similarity(a, twin) > eng.similarity(a, other)
    clusters = eng.cluster({"a": a, "twin": twin, "other": other}, threshold=0.999)
    sizes = sorted(len(c) for c in clusters)
    assert sizes == [1, 2]


def test_cosine_zero_norm_guard() -> None:
    assert _cosine(np.zeros(3), np.ones(3)) == 0.0


def test_alpha_competition_allocates_influence() -> None:
    strong = make_alpha("strong", sharpe=2.0, health_score=95.0)
    weak = make_alpha("weak", sharpe=0.3, health_score=50.0, decay_multiplier=0.5)
    result = AlphaCompetitionEngine().compete([strong, weak])
    assert abs(sum(result.influence.values()) - 1.0) < 1e-9
    assert result.influence["strong"] > result.influence["weak"]
    assert result.ranking[0] == "strong"


def test_alpha_competition_zero_when_no_strength() -> None:
    dead = make_alpha("dead", sharpe=0.0, health_score=0.0)
    result = AlphaCompetitionEngine().compete([dead])
    assert result.influence == {"dead": 0.0}


def test_stress_signal_engine_flags_fragility() -> None:
    eng = StressSignalEngine(fragility_threshold=60.0)
    robust = eng.assess(volatility_shock=0.1, liquidity_shock=0.1, regime_change=0.1,
                        correlation_breakdown=0.1)
    fragile = eng.assess(volatility_shock=0.9, liquidity_shock=0.9, regime_change=0.9,
                         correlation_breakdown=0.9)
    assert robust.survived
    assert robust.robustness_score > fragile.robustness_score
    assert not fragile.survived
    assert abs(fragile.fragility_score + fragile.robustness_score - 100.0) < 1e-9
