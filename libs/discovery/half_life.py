"""alpha_half_life_engine — expected lifespan and decay probability.

Fits the trend of an alpha's rolling performance: a flat/rising series implies a long half-life;
a declining one implies decay. Ranking uses Expected CAGR x Expected Lifespan, so durable edges
are preferred over flashy ones.
"""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel, ConfigDict


class HalfLifeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    half_life_days: float
    decay_probability: float  # 0-1
    declining: bool


def alpha_half_life(
    rolling_performance: np.ndarray, *, period_days: float = 1.0, cap_days: float = 3650.0
) -> HalfLifeResult:
    """Estimate half-life from the slope of a rolling-performance series."""
    perf = np.asarray(rolling_performance, dtype="float64")
    n = len(perf)
    if n < 3:
        return HalfLifeResult(half_life_days=cap_days, decay_probability=0.0, declining=False)
    t = np.arange(n, dtype="float64")
    slope = float(np.polyfit(t, perf, 1)[0])
    level = float(perf.mean())
    decay_probability = float(1.0 / (1.0 + math.exp(slope * 50.0)))  # steeper decline -> higher

    if slope >= 0 or level <= 0:
        half_life = cap_days
        declining = False
    else:
        periods_to_half = (0.5 * level) / (-slope)
        half_life = min(cap_days, max(0.0, periods_to_half) * period_days)
        declining = True

    return HalfLifeResult(
        half_life_days=half_life, decay_probability=decay_probability, declining=declining
    )
