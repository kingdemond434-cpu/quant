"""Exposure aggregation — factor, strategy, asset-class, symbol, and risk contributions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.models import AlphaInput
from libs.risk.risk_budget import risk_contributions


def _group(weights: Mapping[str, float], key_of: Mapping[str, str | None]) -> dict[str, float]:
    out: dict[str, float] = {}
    for alpha_id, weight in weights.items():
        key = key_of.get(alpha_id)
        if key is None:
            continue
        out[key] = out.get(key, 0.0) + float(weight)
    return out


def calculate_factor_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.factor.value for a in alphas})


def calculate_strategy_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.strategy_type.value for a in alphas})


def calculate_asset_class_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.asset_class for a in alphas})


def calculate_symbol_exposures(
    weights: Mapping[str, float], alphas: Sequence[AlphaInput]
) -> dict[str, float]:
    return _group(weights, {a.alpha_id: a.symbol for a in alphas})


def calculate_risk_contributions(
    weights: Mapping[str, float], cov: np.ndarray, order: Sequence[str]
) -> dict[str, float]:
    """Fractional risk contributions (sum to 1) per alpha, in ``order``."""
    w = np.array([weights[i] for i in order], dtype="float64")
    rc = risk_contributions(w, np.asarray(cov, dtype="float64"))
    total = float(rc.sum())
    if total <= 0:
        return dict.fromkeys(order, 0.0)
    return {i: float(rc[k] / total) for k, i in enumerate(order)}
