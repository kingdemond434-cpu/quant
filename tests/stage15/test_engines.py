"""Stage 15 engines: economic mechanism, regime validation, contribution, priority, scoring."""

from __future__ import annotations

import pytest
from tests.stage15.conftest import good_scores

from libs.stage15.contribution import AlphaContributionForecaster
from libs.stage15.economic_mechanism import EconomicMechanismEngine
from libs.stage15.models import MechanismType, ResearchRegime
from libs.stage15.priority import ResearchCandidate, ResearchPriorityEngine
from libs.stage15.regime_validation import RegimeValidationEngine
from libs.stage15.scoring import alpha_quality_score

_FULL_PRIOR = {
    "mechanism": "behavioral",
    "why_it_works": "underreaction to news",
    "why_it_might_fail": "crowding",
    "why_overfit": "many params",
    "why_decay": "arbitraged away",
    "how_detect_decay": "rolling sharpe",
    "what_replaces_it": "successor v2",
}


def test_economic_mechanism_required() -> None:
    eng = EconomicMechanismEngine()
    full = eng.require(_FULL_PRIOR)
    assert full.present
    assert full.mechanism is MechanismType.BEHAVIORAL
    # missing fields -> no documented mechanism -> reject
    incomplete = eng.require({"mechanism": "behavioral"})
    assert not incomplete.present
    assert incomplete.missing
    assert not eng.has_mechanism({})
    # an unrecognized mechanism string resolves to no typed mechanism
    bogus = eng.require({**_FULL_PRIOR, "mechanism": "magic"})
    assert bogus.mechanism is None


def test_regime_validation_prefers_broad_survival() -> None:
    eng = RegimeValidationEngine()
    broad = eng.validate({
        ResearchRegime.BULL: 70.0, ResearchRegime.BEAR: 65.0, ResearchRegime.HIGH_VOL: 60.0,
        ResearchRegime.LOW_VOL: 62.0, ResearchRegime.CRISIS: 55.0,
    })
    narrow = eng.validate({
        ResearchRegime.BULL: 90.0, ResearchRegime.BEAR: 5.0, ResearchRegime.CRISIS: 0.0,
    })
    assert broad.regime_resilience_score > narrow.regime_resilience_score
    assert broad.productive_fraction > narrow.productive_fraction
    assert "bull" in broad.by_regime


def test_contribution_forecaster_rewards_diversification() -> None:
    eng = AlphaContributionForecaster(max_correlation=0.6)
    diversifying = eng.forecast(
        alpha_return=0.1, alpha_sharpe=1.5, weight=0.2, survival_score=90.0,
        correlations_to_book=[0.05, 0.1],
    )
    redundant = eng.forecast(
        alpha_return=0.1, alpha_sharpe=1.5, weight=0.2, survival_score=90.0,
        correlations_to_book=[0.9, 0.85],
    )
    assert diversifying.diversification_benefit > redundant.diversification_benefit
    assert diversifying.net_beneficial
    assert not redundant.net_beneficial  # too correlated to the book


def test_research_priority_ranks_high_ev_low_corr() -> None:
    eng = ResearchPriorityEngine()
    ranked = eng.rank([
        ResearchCandidate(hypothesis_id="weak", expected_edge=0.2, correlation_to_existing=0.9),
        ResearchCandidate(hypothesis_id="strong", expected_edge=0.9,
                          correlation_to_existing=0.1, capacity=0.8, economic_strength=0.9,
                          regime_diversification_potential=0.8),
    ])
    assert ranked[0].hypothesis_id == "strong"
    assert 0.0 <= ranked[-1].research_priority_score <= 100.0


def test_alpha_quality_excludes_raw_return() -> None:
    base = good_scores()
    # doubling raw expected_return must NOT change the quality score (durability, not returns)
    pumped = good_scores(expected_return=base.expected_return * 5)
    assert alpha_quality_score(base).score == pytest.approx(alpha_quality_score(pumped).score)
    # weak survival must lower quality
    weak = good_scores(survival_score=10.0)
    assert alpha_quality_score(weak).score < alpha_quality_score(base).score
