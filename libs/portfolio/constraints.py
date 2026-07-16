"""Portfolio constraints — per-weight, factor, strategy, and asset-class caps.

Per-weight caps use water-filling (cap and redistribute, preserving sum = 1). Group caps scale
the offending group down (any freed weight stays uninvested rather than forcing a re-breach).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from libs.portfolio.models import AlphaInput, PortfolioConstraints

_EPS = 1e-9


def _cap_per_weight(weights: dict[str, float], max_weight: float) -> bool:
    """Water-fill per-weight cap, keeping the total constant. Returns whether any cap bound."""
    bound = False
    for _ in range(100):
        over = {i: w for i, w in weights.items() if w > max_weight + _EPS}
        if not over:
            break
        bound = True
        excess = sum(w - max_weight for w in over.values())
        for i in over:
            weights[i] = max_weight
        under = {i: weights[i] for i in weights if i not in over}
        headroom = sum(max(0.0, max_weight - w) for w in under.values())
        if headroom <= _EPS:
            break
        for i in under:
            room = max(0.0, max_weight - weights[i])
            weights[i] += excess * room / headroom
    return bound


def apply_constraints(
    weights: Mapping[str, float],
    alphas: Sequence[AlphaInput],
    constraints: PortfolioConstraints,
) -> tuple[dict[str, float], list[str]]:
    """Enforce long-only, per-weight, and group caps; return weights + binding constraint labels."""
    amap = {a.alpha_id: a for a in alphas}
    w = {i: float(v) for i, v in weights.items()}
    binding: set[str] = set()

    if constraints.long_only:
        for i in w:
            if w[i] < 0:
                w[i] = 0.0
                binding.add(f"long_only:{i}")

    if constraints.sum_to_one:
        total = sum(w.values())
        if total > 0:
            for i in w:
                w[i] /= total

    if _cap_per_weight(w, constraints.max_weight):
        binding.add("max_weight")

    for group_type, cap in (
        ("factor", constraints.max_factor_weight),
        ("strategy", constraints.max_strategy_weight),
        ("asset_class", constraints.max_asset_class_weight),
    ):
        keys: dict[str, str | None] = {i: _key_of(group_type, amap[i]) for i in w}
        totals: dict[str, float] = {}
        for i, key in keys.items():
            if key is not None:
                totals[key] = totals.get(key, 0.0) + w[i]
        for key, total in totals.items():
            if total > cap + _EPS and total > 0:
                scale = cap / total
                for i, alpha_key in keys.items():
                    if alpha_key == key:
                        w[i] *= scale
                binding.add(f"{group_type}:{key}")

    return w, sorted(binding)


def _key_of(group_type: str, alpha: AlphaInput) -> str | None:
    if group_type == "factor":
        return alpha.factor.value
    if group_type == "strategy":
        return alpha.strategy_type.value
    return alpha.asset_class
