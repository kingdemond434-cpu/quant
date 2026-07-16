"""Research prioritization — test the most durable, least-crowded families first.

Higher-priority families historically hold more durable, less-crowded institutional edge (carry,
risk premia, cross-asset, regime, liquidity) than retail-style technical systems (trend, momentum,
breakout, mean reversion). The lab orders its hypothesis queue by this priority so scarce research
throughput is spent where genuine edge is more likely. Priority affects ORDER only — never the
validation thresholds, which are identical for every family.
"""

from __future__ import annotations

from collections.abc import Sequence

from libs.autodiscovery.generators import GeneratorSpec
from libs.autodiscovery.models import Family, Hypothesis

# Lower rank value = higher priority (tested first).
FAMILY_PRIORITY: dict[Family, int] = {
    Family.CARRY: 0,
    Family.RISK_PREMIA: 1,
    Family.CROSS_ASSET: 2,
    Family.REGIME_TRANSITION: 3,
    Family.LIQUIDITY: 4,
    Family.SESSION: 5,
    Family.VOLATILITY_EXPANSION: 6,
    Family.VOLATILITY_COMPRESSION: 7,
    Family.TREND: 8,
    Family.MOMENTUM: 9,
    Family.BREAKOUT: 10,
    Family.MEAN_REVERSION: 11,
}


def family_rank(family: Family) -> int:
    return FAMILY_PRIORITY.get(family, 99)


def prioritize(
    plan: Sequence[tuple[Hypothesis, GeneratorSpec]],
) -> list[tuple[Hypothesis, GeneratorSpec]]:
    """Stable-sort a hypothesis plan by family priority (highest-priority families first)."""
    return sorted(plan, key=lambda pair: family_rank(pair[0].family))
