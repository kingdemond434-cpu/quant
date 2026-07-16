"""Signal attribution, champion/challenger, and shadow deployment."""

from __future__ import annotations

import pytest

from libs.signal_engine.attribution import SignalAttributionEngine
from libs.signal_engine.champion_challenger import ChampionChallenger, VariantMetrics
from libs.signal_engine.models import Direction
from libs.signal_engine.shadow import ShadowDeployment


def test_attribution_splits_return_by_weight() -> None:
    res = SignalAttributionEngine().attribute(
        alpha_weights={"trend": 0.75, "momentum": 0.25}, realized_return=0.04
    )
    assert res.by_alpha["trend"] == pytest.approx(0.03)
    assert res.by_alpha["momentum"] == pytest.approx(0.01)
    assert res.total_return == pytest.approx(0.04)
    assert res.top_contributor == "trend"


def test_attribution_detailed_winners_and_losers() -> None:
    res = SignalAttributionEngine().attribute_detailed(
        alpha_weights={"a": 0.5, "b": 0.5},
        alpha_returns={"a": 0.10, "b": -0.04},
    )
    assert res.by_alpha["a"] == pytest.approx(0.05)
    assert res.by_alpha["b"] == pytest.approx(-0.02)
    assert res.winners == ["a"]
    assert res.losers == ["b"]
    assert res.top_detractor == "b"


def test_attribution_zero_weight_safe() -> None:
    res = SignalAttributionEngine().attribute(alpha_weights={"a": 0.0}, realized_return=0.05)
    assert res.by_alpha == {"a": 0.0}


def _champion() -> VariantMetrics:
    return VariantMetrics(variant_id="champ", sharpe=1.0, profit_factor=1.5, turnover=0.2,
                          max_drawdown=0.10, n_samples=500)


def test_champion_challenger_promotes_clear_winner() -> None:
    cc = ChampionChallenger(min_samples=100, min_sharpe_uplift=0.1)
    challenger = VariantMetrics(variant_id="chal", sharpe=1.4, profit_factor=1.7, turnover=0.2,
                                max_drawdown=0.09, n_samples=300)
    result = cc.compare(_champion(), challenger, challenger_walk_forward_passed=True)
    assert result.promote is True
    assert result.winner_id == "chal"


def test_champion_challenger_fail_closed_without_walk_forward() -> None:
    cc = ChampionChallenger()
    challenger = VariantMetrics(variant_id="chal", sharpe=2.0, profit_factor=2.0, turnover=0.2,
                                max_drawdown=0.05, n_samples=999)
    result = cc.compare(_champion(), challenger, challenger_walk_forward_passed=False)
    assert result.promote is False  # never promote without walk-forward pass
    assert result.winner_id == "champ"


def test_champion_challenger_rejects_worse_drawdown() -> None:
    cc = ChampionChallenger(max_drawdown_ratio=1.1)
    challenger = VariantMetrics(variant_id="chal", sharpe=1.5, profit_factor=1.6, turnover=0.2,
                                max_drawdown=0.20, n_samples=500)  # dd far worse
    result = cc.compare(_champion(), challenger, challenger_walk_forward_passed=True)
    assert result.promote is False


def test_shadow_deployment_tracks_without_capital() -> None:
    shadow = ShadowDeployment("challenger_v2")
    for _ in range(60):
        shadow.observe(
            production_direction=Direction.BUY, shadow_direction=Direction.BUY,
            production_return=0.01, shadow_return=0.012,
        )
    shadow.observe(
        production_direction=Direction.BUY, shadow_direction=Direction.FLAT,
        production_return=0.01, shadow_return=0.0,
    )
    result = shadow.result(min_decisions=50)
    assert result.n_decisions == 61
    assert 0.0 < result.agreement_rate < 1.0
    assert result.shadow_return > 0
    assert result.tracking_error >= 0
    assert result.ready_for_promotion is True  # readiness only; no capital is ever allocated


def test_shadow_empty_is_not_ready() -> None:
    result = ShadowDeployment("v").result(min_decisions=10)
    assert result.n_decisions == 0
    assert result.ready_for_promotion is False
