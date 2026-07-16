"""Alpha lifecycle primitives: decay state, promotion ladder, replacement committee, research ROI.

Pure, tested functions that decide which sleeves live, scale, or die -- the governance layer above
allocation. Kept numeric/stateless so they wire onto the shadow + portfolio JSON. Conservative by
design: replacement defaults to KEEP-BOTH, promotion never auto-reaches production, and decay needs
real rolling windows (returns 'accumulating' until they exist) so nothing is retired on noise.
"""

from __future__ import annotations

# research -> ... -> production. A sleeve may not skip stages.
LADDER = ["research", "backtest", "validation", "shadow", "testnet", "small_capital", "production"]
HEALTH = ["Healthy", "Watchlist", "Degraded", "Retire", "Accumulating"]


def decay_state(rolling: dict[str, float | None], expected: float | None) -> str:
    """Health from rolling 30/60/90d Sharpe vs the validated expectation. Worst window drives it:
    >=60% below (or negative) -> Retire, >=40% -> Degraded, >=20% -> Watchlist, else Healthy.
    Returns 'Accumulating' until at least one rolling window exists."""
    vals = [v for v in rolling.values() if v is not None]
    if not vals:
        return "Accumulating"
    if expected is None or expected <= 0:
        return "Accumulating"
    worst = min(vals)
    drop = 1.0 - worst / expected
    if worst < 0 or drop >= 0.6:
        return "Retire"
    if drop >= 0.4:
        return "Degraded"
    if drop >= 0.2:
        return "Watchlist"
    return "Healthy"


def promotion_stage(days_shadow: int, fwd_sharpe: float | None, gates_passed: int,
                    n_gates: int, *, min_shadow: int = 90) -> str:
    """Where a sleeve sits on the ladder. Conservative: stays in 'shadow' until it has both the full
    forward window AND a positive forward Sharpe; never auto-promotes past small_capital."""
    if n_gates and gates_passed < 0.6 * n_gates:
        return "research"
    if fwd_sharpe is None or days_shadow < min_shadow or fwd_sharpe < 0.5:
        return "shadow"
    if days_shadow < int(1.5 * min_shadow):
        return "testnet"
    return "small_capital"


def replacement_decision(current: dict[str, float], candidate: dict[str, float],
                         correlation: float) -> str:
    """Replacement committee. Default KEEP-BOTH (additive alpha is valuable). Only REPLACE when the
    candidate dominates on Sharpe AND CAGR AND capacity AND is highly correlated (>0.7) to the
    incumbent (i.e. a strictly better version of the same bet). Otherwise REJECT or keep both."""
    dominates = (candidate.get("sharpe", 0.0) > current.get("sharpe", 0.0)
                 and candidate.get("cagr", 0.0) >= current.get("cagr", 0.0)
                 and candidate.get("capacity", 0.0) >= current.get("capacity", 0.0))
    if not dominates:
        return "reject"
    return "replace" if correlation > 0.7 else "keep_both"


def research_roi(benefit: float, p_success: float, effort: float) -> float:
    """ROI score = (expected portfolio benefit x P(success)) / engineering effort."""
    return round(benefit * p_success / effort, 3) if effort > 0 else 0.0


def rank_by_roi(items: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    """Rank research candidates by ROI score (each item needs benefit, p_success, effort)."""
    for it in items:
        it["roi"] = research_roi(float(it["benefit"]), float(it["p_success"]), float(it["effort"]))
    return sorted(items, key=lambda d: -float(d["roi"]))
