"""Tests for health monitoring, decay detection, ranking, and successor recommendation."""

from __future__ import annotations

from tests.alpha.conftest import make_card, make_expected, make_live

from libs.alpha.decay import detect_decay
from libs.alpha.health import calculate_alpha_health
from libs.alpha.ranking import rank_alphas
from libs.alpha.state import AlphaState
from libs.alpha.successor import recommend_successors

# --- health ---------------------------------------------------------------


def test_health_perfect_when_live_meets_expected() -> None:
    health = calculate_alpha_health(make_expected(), make_live())
    assert health.healthy
    assert health.overall >= 0.99


def test_health_degrades_when_live_underperforms() -> None:
    live = make_live(
        sharpe=0.3, cagr=0.05, max_drawdown=0.30, win_rate=0.35, profit_factor=0.8,
        expectancy=0.05, regime_stability=0.4,
    )
    health = calculate_alpha_health(make_expected(), live)
    assert not health.healthy
    assert health.components["sharpe"] < 0.5
    assert health.components["drawdown_divergence"] < 1.0


def test_health_skips_missing_baselines() -> None:
    expected = make_expected(win_rate=None, profit_factor=None, expectancy=None)
    health = calculate_alpha_health(expected, make_live())
    assert "win_rate" not in health.components
    assert "sharpe" in health.components


def test_regime_sensitivity_reflected() -> None:
    health = calculate_alpha_health(make_expected(), make_live(regime_stability=0.2))
    assert health.components["regime_sensitivity"] == 0.2


# --- decay ----------------------------------------------------------------


def test_decay_low_when_healthy() -> None:
    result = detect_decay(make_expected(), make_live())
    assert result.decay_score < 0.30
    assert result.recommended_state is AlphaState.ACTIVE


def test_decay_escalates_with_deterioration() -> None:
    live = make_live(
        sharpe=0.1, cagr=0.0, max_drawdown=0.35, profit_factor=0.7,
        expectancy=0.0, win_rate=0.4, regime_stability=0.2,
    )
    result = detect_decay(make_expected(), live)
    assert result.decay_score > 0.5
    assert result.recommended_state in {AlphaState.DECAYING, AlphaState.RETIREMENT_CANDIDATE}
    assert 0.0 <= result.decay_score <= 1.0


# --- ranking --------------------------------------------------------------


def test_ranking_orders_by_quality() -> None:
    strong = make_card(live_sharpe=2.0, decay_score=0.0, pbo=0.1)
    weak = make_card(live_sharpe=0.5, decay_score=0.6, pbo=0.4)
    ranked = rank_alphas([weak, strong])
    assert ranked[0].alpha_id == strong.id
    assert ranked[0].rank == 1
    assert ranked[0].score > ranked[1].score


# --- successors -----------------------------------------------------------


def test_successor_recommendation_filters_and_ranks() -> None:
    decaying = make_card(market="XAUUSD", category="session", status=AlphaState.DECAYING)
    same_market = make_card(market="XAUUSD", category="trend", live_sharpe=1.8)
    same_category = make_card(market="EURUSD", category="session", live_sharpe=1.2)
    unrelated = make_card(market="BTCUSD", category="momentum", live_sharpe=3.0)
    retired = make_card(market="XAUUSD", category="session", status=AlphaState.RETIRED,
                        live_sharpe=5.0)
    candidates = [decaying, same_market, same_category, unrelated, retired]
    successors = recommend_successors(candidates, decaying, top_n=3)
    ids = [c.id for c in successors]
    assert same_market.id in ids
    assert same_category.id in ids
    assert unrelated.id not in ids  # different market and category
    assert retired.id not in ids    # retired excluded
