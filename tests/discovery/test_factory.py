"""Tests for the Alpha Discovery Factory orchestrator (honest-skeptic behavior)."""

from __future__ import annotations

from tests.discovery.conftest import make_bars

from libs.discovery.factory import AlphaDiscoveryFactory
from libs.discovery.models import HypothesisCategory

_CATEGORIES = [HypothesisCategory.TREND, HypothesisCategory.MEAN_REVERSION]


def test_factory_runs_and_reports() -> None:
    data = {"XAUUSD": make_bars(drift=0.0, seed=1), "EURUSD": make_bars(drift=0.0, seed=2)}
    factory = AlphaDiscoveryFactory(mc_sims=200, min_observations=60, seed=0)
    report = factory.discover(data, _CATEGORIES)
    assert report.n_generated == 4
    assert report.n_backtested == 4
    assert report.n_accepted == len(report.accepted)
    assert "rejecting noise" in report.error_budget_note


def test_factory_rejects_pure_noise() -> None:
    # The whole point of the gauntlet: random data must not yield "discoveries".
    data = {"XAUUSD": make_bars(drift=0.0, vol=0.01, seed=11)}
    factory = AlphaDiscoveryFactory(mc_sims=200, seed=0)
    report = factory.discover(data, _CATEGORIES)
    assert report.n_accepted == 0


def test_factory_candidate_carries_evidence_and_reasons() -> None:
    factory = AlphaDiscoveryFactory(mc_sims=200, seed=0)
    bars = make_bars(drift=0.0, seed=21)
    hypotheses = factory  # access the internal evaluation for one hypothesis
    from libs.discovery.hypotheses import HypothesisGenerator

    hyp = HypothesisGenerator().generate(["XAUUSD"], [HypothesisCategory.TREND])[0]
    candidate = hypotheses._evaluate(hyp, bars)
    assert candidate.hypothesis.id == hyp.id
    assert candidate.robustness.survival_probability >= 0.0
    if not candidate.accepted:
        assert candidate.rejection_reasons  # rejected candidates explain why


def test_factory_only_searches_available_symbols() -> None:
    data = {"XAUUSD": make_bars(seed=1)}
    factory = AlphaDiscoveryFactory(mc_sims=100, seed=0)
    report = factory.discover(data, [HypothesisCategory.TREND], symbols=["XAUUSD", "NOT_PRESENT"])
    assert report.n_generated == 1  # only the available symbol is searched
