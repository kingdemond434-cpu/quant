"""Automatic, economically-anchored hypothesis generation.

Hypotheses are template instantiations within economically-motivated regions (the research
categories), each carrying a mechanism — never blind feature mining. Default parameters and a
small neighbourhood sweep (for parameter-stability testing) are defined per category.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from libs.core.ids import generate_id
from libs.discovery.models import (
    CATEGORY_FAMILY,
    CATEGORY_MECHANISM,
    AlphaHypothesis,
    HypothesisCategory,
)

DEFAULT_PARAMS: dict[HypothesisCategory, dict[str, Any]] = {
    HypothesisCategory.SESSION: {"session": "london"},
    HypothesisCategory.TREND: {"fast": 10, "slow": 30},
    HypothesisCategory.BREAKOUT: {"window": 20},
    HypothesisCategory.MEAN_REVERSION: {"window": 20, "z": 1.5},
    HypothesisCategory.MOMENTUM: {"lookback": 20},
    HypothesisCategory.RELATIVE_STRENGTH: {"lookback": 20},
    HypothesisCategory.VOL_REGIME: {"window": 20, "mode": "compression"},
    HypothesisCategory.VOL_COMPRESSION: {"window": 20, "mode": "compression"},
    HypothesisCategory.VOL_EXPANSION: {"window": 20, "mode": "expansion"},
    HypothesisCategory.SEASONAL: {"weekday": 0},
    HypothesisCategory.CARRY: {"direction": 1.0},
}


def default_params(category: HypothesisCategory) -> dict[str, Any]:
    return dict(DEFAULT_PARAMS.get(category, {"lookback": 20}))


def param_sweep(category: HypothesisCategory, base: Mapping[str, Any]) -> dict[str, list[Any]]:
    """Neighbouring parameter values used for grid search and parameter-stability testing."""
    if category is HypothesisCategory.TREND:
        fast = int(base["fast"])
        return {"fast": [max(2, fast - 5), fast + 5, fast + 10]}
    if category in (
        HypothesisCategory.BREAKOUT, HypothesisCategory.VOL_REGIME,
        HypothesisCategory.VOL_COMPRESSION, HypothesisCategory.VOL_EXPANSION,
    ):
        w = int(base["window"])
        return {"window": [max(5, w - 10), w + 10, w + 20]}
    if category is HypothesisCategory.MEAN_REVERSION:
        w, z = int(base["window"]), float(base["z"])
        return {"window": [max(5, w - 10), w + 10], "z": [max(0.5, z - 0.5), z + 0.5]}
    if category in (HypothesisCategory.MOMENTUM, HypothesisCategory.RELATIVE_STRENGTH):
        lb = int(base["lookback"])
        return {"lookback": [max(2, lb - 10), lb + 10, lb + 20]}
    if category is HypothesisCategory.SEASONAL:
        wd = int(base["weekday"])
        return {"weekday": [(wd + 1) % 5, (wd + 2) % 5]}
    if category is HypothesisCategory.SESSION:
        return {"session": ["newyork", "asia"]}
    if category is HypothesisCategory.CARRY:
        return {}
    lb = int(base.get("lookback", 20))
    return {"lookback": [max(2, lb - 10), lb + 10, lb + 20]}


class HypothesisGenerator:
    """Generates pre-registered hypotheses across symbols and categories."""

    def generate(
        self, symbols: Sequence[str], categories: Sequence[HypothesisCategory]
    ) -> list[AlphaHypothesis]:
        hypotheses: list[AlphaHypothesis] = []
        for symbol in symbols:
            for category in categories:
                mechanism = CATEGORY_MECHANISM[category]
                hypotheses.append(
                    AlphaHypothesis(
                        id=generate_id("hyp"),
                        name=f"{symbol}_{category.value}",
                        symbol=symbol,
                        category=category,
                        family=CATEGORY_FAMILY[category],
                        mechanism=mechanism,
                        params=default_params(category),
                        rationale=(
                            f"{category.value} edge in {symbol} via a {mechanism.value} mechanism; "
                            "must survive trials-adjusted disproof to be retained."
                        ),
                    )
                )
        return hypotheses
