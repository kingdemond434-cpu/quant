"""Multi-period, cost-aware E[log W]: the allocator plans a path, not a point.

    max_{h_1..h_H}  E[ sum_tau log(1 + h_tau' r_{tau+1}) - c * |h_tau - h_{tau-1}|_1 ]

cvxportfolio's idea with the desk's own world tensor as the scenario set: the sampled worlds'
rows are split into H consecutive blocks, one heat vector per block, and the L1 switching cost
between consecutive blocks is what stops the book oscillating on forecast noise. Projected
subgradient ascent on the same capped simplex the single-period solve uses; `h_1` is the action
now, the rest is the plan that made it cheap.

Two uses. As a CHALLENGER book in the proof contest (`plan(...)["h_now"]`), and as the
principled TRADE VALUE of a proposed rebalance:

    TradeValue = E[log W | move] - E[log W | hold] - c * turnover

which is exactly what `pf_allocator.no_trade` charges, here with the growth difference read off
the worlds rather than a fixed horizon.

A third use, `plan_posterior`: the same inputs and the same book format, solved by
`libs.portfolio.posterior_growth` -- the posterior E[log W] optimiser with the ruin and stop-out
constraints, the flat floor and the winner's-curse shrinkage. `plan` and `plan_posterior` are
challengers to each other on the same worlds, which is how the contest decides whether the
posterior machinery earns its variance.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from libs.portfolio.posterior_growth import DEFAULT_N_PATHS, sample_paths, solve
from libs.portfolio.robust_elog import SleeveEvidence, Worlds


def _project(h: np.ndarray, cap: float, upper: np.ndarray | None) -> np.ndarray:
    ub = np.full_like(h, np.inf) if upper is None else upper
    x: np.ndarray = np.clip(h, 0.0, ub)
    if x.sum() <= cap:
        return x
    lo, hi = float(x.min()) - cap - (float(np.max(ub[np.isfinite(ub)])) if
                                      np.isfinite(ub).any() else 0.0), float(x.max())
    for _ in range(60):
        tau = 0.5 * (lo + hi)
        if np.clip(h - tau, 0.0, ub).sum() > cap:
            lo = tau
        else:
            hi = tau
    out: np.ndarray = np.clip(h - hi, 0.0, ub)
    return out


def _growth_and_grad(block: np.ndarray, h: np.ndarray) -> tuple[float, np.ndarray]:
    port = np.einsum("wtn,n->wt", block, h.astype(np.float32)).astype(np.float64)
    one_plus = 1.0 + port
    if not np.all(one_plus > 1e-9):
        return -np.inf, np.zeros_like(h)
    g = float(np.log(one_plus).mean())
    u = 1.0 / one_plus
    grad = np.einsum("wtn,wt->n", block, (u / u.size).astype(np.float32)).astype(np.float64)
    return g, grad


def plan(worlds: Any, h_prev: Mapping[str, float], *, horizon: int = 4, cost_r: float = 0.06,
         cap: float = 0.30, target: float | None = None,
         upper: Mapping[str, float] | None = None, iterations: int = 150,
         step: float = 0.02) -> dict[str, Any]:
    names = list(worlds.names)
    r = worlds.r
    if r.shape[1] < horizon * 8:
        horizon = max(1, r.shape[1] // 8)
    blocks = np.array_split(np.arange(r.shape[1]), horizon)
    h0 = np.array([float(h_prev.get(k, 0.0)) for k in names])
    ub = None if upper is None else np.array([float(upper.get(k, np.inf)) for k in names])
    hs = [h0.copy() for _ in range(horizon)]
    for _ in range(iterations):
        for t in range(horizon):
            g, grad = _growth_and_grad(r[:, blocks[t], :], hs[t])
            if not np.isfinite(g):
                hs[t] = 0.5 * hs[t]
                continue
            prev = h0 if t == 0 else hs[t - 1]
            nxt = hs[t + 1] if t + 1 < horizon else None
            sub = cost_r * np.sign(hs[t] - prev)
            if nxt is not None:
                sub = sub - cost_r * np.sign(nxt - hs[t])
            cand = hs[t] + step * (grad - sub)
            hs[t] = _project(cand, cap, ub)
            if target is not None and hs[t].sum() < target - 1e-6:
                # the mandate: the path may not sit below the floor
                scale = target / max(hs[t].sum(), 1e-12)
                hs[t] = _project(hs[t] * scale, cap, ub)
    growth = [(_growth_and_grad(r[:, blocks[t], :], hs[t])[0]) for t in range(horizon)]
    turnover = [float(np.abs(hs[0] - h0).sum())] + [float(np.abs(hs[t] - hs[t - 1]).sum())
                                                    for t in range(1, horizon)]
    return {"h_now": {k: round(float(v), 6) for k, v in zip(names, hs[0], strict=True)},
            "path_total_heat": [round(float(h.sum()), 6) for h in hs],
            "growth_per_block": [round(g, 8) if np.isfinite(g) else None for g in growth],
            "turnover_per_block": [round(t, 6) for t in turnover],
            "objective": round(float(sum(g for g in growth if np.isfinite(g))
                                     - cost_r * sum(turnover)), 8),
            "horizon": horizon, "cost_r": cost_r}


def trade_value(worlds: Any, current: Mapping[str, float], proposed: Mapping[str, float],
                *, cost_r: float = 0.06) -> dict[str, Any]:
    """dE[log W] of moving from `current` to `proposed`, less the turnover cost, on the worlds."""
    names = list(worlds.names)
    hc = np.array([float(current.get(k, 0.0)) for k in names])
    hp = np.array([float(proposed.get(k, 0.0)) for k in names])
    gc, _ = _growth_and_grad(worlds.r, hc)
    gp, _ = _growth_and_grad(worlds.r, hp)
    turnover = 0.5 * float(np.abs(hp - hc).sum())
    gain = (gp - gc) if np.isfinite(gp) and np.isfinite(gc) else float("inf")
    value = gain - cost_r * turnover if np.isfinite(gain) else float("inf")
    return {"growth_current": gc, "growth_proposed": gp, "gain_per_day": gain,
            "turnover": round(turnover, 6), "cost": round(cost_r * turnover, 8),
            "trade_value": value, "verdict": "REBALANCE" if value > 0 else "HOLD"}


def plan_posterior(worlds: Worlds, h_prev: Mapping[str, float], *, horizon: int = 4,
                   cost_r: float = 0.06, cap: float = 0.30, target: float | None = None,
                   upper: Mapping[str, float] | None = None,
                   ev: Sequence[SleeveEvidence] | None = None, n_paths: int = DEFAULT_N_PATHS,
                   seed: int = 0, iterations: int = 300, step: float = 0.05) -> dict[str, Any]:
    """`plan`'s inputs, `plan`'s book format, solved by the posterior E[log W] optimiser.

    WHY A SECOND PLANNER RATHER THAN A CHANGE TO THE FIRST. `plan` maximises sample-average growth
    of a schedule on the world tensor and knows nothing about ruin, stop-out, or how much of a
    sleeve's measured edge the evidence actually supports; that is what makes it a fair, simple
    rival. `posterior_growth.solve` takes the SAME worlds as its scenario population (T-day blocks
    cut from them, so regime mix and crisis overlay are the desk's own) and adds the two
    probabilistic constraints, the flat floor and the shrinkage. Returning both in one format lets
    the contest score them side by side, which is rule 1 applied to the planner itself: the
    posterior machinery keeps its seat only by beating the plain plan on the worlds it shares.

    `target` is the flat floor (`plan` calls it the mandate), `cap` the ceiling, `upper` the
    per-sleeve caps. The plan for the later blocks is to HOLD the first step -- the receding
    horizon re-solves before block two arrives -- so every block after the first reports zero
    turnover and the same total heat. `ev`, when given, supplies each sleeve's round-trip cost and
    the shrinkage summary the certificate carries; without it costs are `cost_r` alone.
    """
    floor = 0.0 if target is None else float(target)
    paths = sample_paths(ev, n_paths=n_paths, horizon=horizon, worlds=worlds, seed=seed)
    book = solve(ev, h_prev=h_prev, paths=paths, floor=floor, ceiling=float(cap), caps=upper,
                 turnover_cost=cost_r, iterations=iterations, step=step)
    names = list(paths.names)
    h = np.array([float(book.h.get(k, 0.0)) for k in names])
    one_plus = 1.0 + np.einsum("mtn,n->mt", paths.r, h)
    growth: list[float | None] = []
    for t in range(paths.horizon):
        col = one_plus[:, t]
        growth.append(round(float(np.log(col).mean()), 8) if bool(np.all(col > 1e-9)) else None)
    fin = [g for g in growth if g is not None]
    return {"h_now": {k: round(float(v), 6) for k, v in book.h.items()},
            "path_total_heat": [round(book.total_heat, 6)] * paths.horizon,
            "growth_per_block": growth,
            "turnover_per_block": [round(book.turnover_l1, 6)] + [0.0] * (paths.horizon - 1),
            "objective": round(float(sum(fin)) - book.turnover_cost, 8),
            "horizon": paths.horizon, "cost_r": cost_r,
            "binding": book.binding, "certificate": book.certificate()}
