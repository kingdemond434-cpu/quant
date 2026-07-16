"""Alpha health monitoring — live vs expected, drift, and regime sensitivity.

Each component is a health score in [0, 1] (1 = meeting or beating expectation). The overall
health is the mean of the available components. Components with no expected baseline are skipped.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from libs.alpha.card import ExpectedMetrics, LiveMetrics


class AlphaHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    overall: float
    healthy: bool
    components: dict[str, float]

    def __bool__(self) -> bool:
        return self.healthy


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _higher_better(live: float | None, expected: float | None) -> float | None:
    """Health where a higher metric is better (sharpe, cagr, win rate, ...)."""
    if expected is None or live is None:
        return None
    if expected <= 0:
        return 1.0 if live >= expected else 0.0
    return _clip01(live / expected)


def _lower_better(live: float | None, expected: float | None) -> float | None:
    """Health where a lower metric is better (drawdown magnitude)."""
    if expected is None or live is None:
        return None
    if live <= 0:
        return 1.0
    if expected <= 0:
        return 0.0
    return _clip01(expected / live)


def calculate_alpha_health(
    expected: ExpectedMetrics, live: LiveMetrics, *, threshold: float = 0.6
) -> AlphaHealth:
    """Compute per-component health (live vs expected) and an overall score."""
    components: dict[str, float] = {}

    def add(name: str, value: float | None) -> None:
        if value is not None:
            components[name] = value

    add("sharpe", _higher_better(live.sharpe, expected.sharpe))
    add("cagr", _higher_better(live.cagr, expected.cagr))
    add("win_rate", _higher_better(live.win_rate, expected.win_rate))
    add("profit_factor", _higher_better(live.profit_factor, expected.profit_factor))
    add("expectancy", _higher_better(live.expectancy, expected.expectancy))
    add("drawdown_divergence", _lower_better(live.max_drawdown, expected.max_drawdown))
    add("regime_sensitivity", _clip01(live.regime_stability))

    if (
        expected.trade_mean is not None
        and expected.trade_std
        and live.trade_mean is not None
    ):
        shift = abs(live.trade_mean - expected.trade_mean) / expected.trade_std
        components["trade_distribution"] = _clip01(1.0 - shift)

    overall = sum(components.values()) / len(components) if components else 1.0
    return AlphaHealth(overall=overall, healthy=overall >= threshold, components=components)
