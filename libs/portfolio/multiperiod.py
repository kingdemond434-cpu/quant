"""Multi-period, cost-aware portfolio glide path.

Single-period optimization ignores the cost of getting from the current book to the target. This
optimizer trades from ``current`` to ``target`` over ``n_steps``, capping turnover per step and
accounting for turnover cost, so rebalancing is gradual and cost-aware. Deterministic; respects the
per-name max-weight constraint at every step. It plans weights — the Portfolio/Risk engines remain
the approvers of any change.

COST NOW CHANGES THE PATH, NOT ONLY THE REPORT (2026-10-06). Until then `cost_per_turnover` was
summed after the glide, so a prohibitive cost and a free one produced the identical path. Each
step now weighs the turnover cost of closing the gap against what being off target costs over the
steps that remain (`tracking_cost_per_step` per unit of gap per step): a unit of gap closed now
saves that cost on every remaining step, so the step is taken only while
`tracking_cost_per_step * steps_left > cost_per_turnover`. A cheap move is made at once (up to the
turnover cap), a dear one is deferred and, when it never pays inside the horizon, not made at all.
This is still a glide toward a GIVEN target; the planner that chooses the target, with returns,
decay, forecasts and later opportunities, is `multiperiod_worlds.plan_receding`.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import PortfolioConstraints


class MultiPeriodPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: list[dict[str, float]] = Field(default_factory=list)  # weights per step
    step_turnover: list[float] = Field(default_factory=list)    # L1/2 turnover per step
    total_cost: float = 0.0


def _turnover(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    keys = set(a) | set(b)
    return 0.5 * sum(abs(b.get(k, 0.0) - a.get(k, 0.0)) for k in keys)


class MultiPeriodOptimizer:
    """Plans a turnover-bounded, cost-aware glide path from current to target weights."""

    def __init__(
        self,
        *,
        constraints: PortfolioConstraints | None = None,
        cost_per_turnover: float = 0.0005,
        max_step_turnover: float = 0.20,
        tracking_cost_per_step: float = 0.01,
    ) -> None:
        self.constraints = constraints or PortfolioConstraints()
        self.cost_per_turnover = cost_per_turnover
        self.max_step_turnover = max_step_turnover
        self.tracking_cost_per_step = tracking_cost_per_step

    def plan(
        self,
        *,
        current: Mapping[str, float],
        target: Mapping[str, float],
        n_steps: int,
    ) -> MultiPeriodPlan:
        if n_steps < 1:
            raise PortfolioError("n_steps must be >= 1")
        keys = sorted(set(current) | set(target))
        cur = {k: float(current.get(k, 0.0)) for k in keys}
        tgt = {k: self._cap(float(target.get(k, 0.0))) for k in keys}

        path: list[dict[str, float]] = []
        step_turnover: list[float] = []
        total_cost = 0.0
        for step in range(n_steps):
            full_move = _turnover(cur, tgt)
            # Closing a unit of gap now saves its tracking cost on every step left in the
            # horizon (this one included); it is worth its turnover cost only while that exceeds
            # the price of trading it. Otherwise the book holds -- an economic decision, not a
            # cosmetic one, and the reason a dearer market produces a different path.
            if self.tracking_cost_per_step * (n_steps - step) <= self.cost_per_turnover:
                path.append(dict(cur))
                step_turnover.append(0.0)
                continue
            # Fraction of the remaining gap we may close this step (turnover-bounded).
            frac = 1.0 if full_move <= self.max_step_turnover or full_move <= 0.0 \
                else self.max_step_turnover / full_move
            # Interpolate toward the (already capped) target; gliding between a current weight and
            # a capped target never exceeds the cap, so each step stays turnover-bounded.
            nxt = {k: cur[k] + frac * (tgt[k] - cur[k]) for k in keys}
            moved = _turnover(cur, nxt)
            step_turnover.append(moved)
            total_cost += moved * self.cost_per_turnover
            path.append(nxt)
            cur = nxt
            if _turnover(cur, tgt) <= 1e-12:
                break
        return MultiPeriodPlan(path=path, step_turnover=step_turnover, total_cost=total_cost)

    def _cap(self, w: float) -> float:
        return max(self.constraints.min_weight, min(self.constraints.max_weight, w))
