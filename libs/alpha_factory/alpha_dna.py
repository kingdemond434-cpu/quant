"""Alpha DNA — a structural fingerprint of an alpha.

The DNA captures *what kind* of strategy an alpha is (signal type, horizon, factor/regime
sensitivities, capacity, turnover, risk). It powers similarity, embedding, and "what makes
winners win" analysis. ``AlphaDNA`` itself lives in ``models``; this module builds and compares.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from libs.alpha_factory.models import AlphaDNA


def build_alpha_dna(
    *,
    signal_type: str,
    market: str,
    timeframe: str,
    holding_period: str,
    factor_exposures: Mapping[str, float] | None = None,
    regime_affinity: Mapping[str, float] | None = None,
    volatility_sensitivity: float = 0.0,
    trend_sensitivity: float = 0.0,
    mean_reversion_sensitivity: float = 0.0,
    capacity_estimate: float = 0.0,
    turnover_profile: float = 0.0,
    risk_profile: float = 0.0,
) -> AlphaDNA:
    """Construct an :class:`AlphaDNA` profile."""
    return AlphaDNA(
        signal_type=signal_type,
        market=market,
        timeframe=timeframe,
        holding_period=holding_period,
        factor_exposures=dict(factor_exposures or {}),
        regime_affinity=dict(regime_affinity or {}),
        volatility_sensitivity=volatility_sensitivity,
        trend_sensitivity=trend_sensitivity,
        mean_reversion_sensitivity=mean_reversion_sensitivity,
        capacity_estimate=capacity_estimate,
        turnover_profile=turnover_profile,
        risk_profile=risk_profile,
    )


def dna_distance(a: AlphaDNA, b: AlphaDNA) -> float:
    """Euclidean distance between two DNA scalar-gene vectors (0 = identical genes)."""
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a.numeric_vector(), b.numeric_vector(),
                                                       strict=True)))
