"""Tests for hypothesis generation and causal signal generators."""

from __future__ import annotations

import numpy as np
from tests.discovery.conftest import make_bars

from libs.discovery.hypotheses import HypothesisGenerator
from libs.discovery.models import HypothesisCategory
from libs.discovery.signals import build_generator


def test_hypothesis_generation() -> None:
    hyps = HypothesisGenerator().generate(
        ["XAUUSD", "BTCUSD"], [HypothesisCategory.SESSION, HypothesisCategory.TREND]
    )
    assert len(hyps) == 4
    assert len({h.id for h in hyps}) == 4
    for h in hyps:
        assert h.mechanism is not None
        assert h.rationale


def test_trend_generator_is_long_only_binary() -> None:
    bars = make_bars(drift=0.001, seed=1)
    targets = build_generator(HypothesisCategory.TREND, {"fast": 10, "slow": 30})(bars)
    assert len(targets) == len(bars)
    assert set(np.unique(targets)) <= {0.0, 1.0}


def test_session_generator_binary() -> None:
    bars = make_bars(seed=2)
    targets = build_generator(HypothesisCategory.SESSION, {"session": "london"})(bars)
    assert set(np.unique(targets)) <= {0.0, 1.0}


def test_fallback_generator_runs() -> None:
    bars = make_bars(seed=3)
    targets = build_generator(HypothesisCategory.LEAD_LAG, {"lookback": 20})(bars)
    assert len(targets) == len(bars)


def test_signals_are_causal() -> None:
    bars = make_bars(n=200, drift=0.0008, seed=4)
    gen = build_generator(HypothesisCategory.TREND, {"fast": 10, "slow": 30})
    base = gen(bars)
    t = 100
    mutated = bars.copy()
    future = mutated.index[t + 1 :]
    mutated.loc[future, ["open", "high", "low", "close"]] = (
        mutated.loc[future, ["open", "high", "low", "close"]] * 5.0
    )
    perturbed = gen(mutated)
    assert np.array_equal(base[: t + 1], perturbed[: t + 1])  # past unaffected by the future
