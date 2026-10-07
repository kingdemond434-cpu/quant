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
from itertools import pairwise
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


# =================================================================================================
# RECEDING-HORIZON OPTIMISATION (2026-10-06)
#
# WHAT `plan` AND `libs.portfolio.multiperiod` DID NOT DO. `multiperiod.MultiPeriodOptimizer` only
# interpolates toward a target it is handed, under a turnover cap: its `cost_per_turnover` changes
# the cost it REPORTS, never the path it takes, so it cannot decide that a move is not worth
# making. `plan` above splits one world tensor into H blocks drawn from the SAME distribution, so
# every block looks like every other: nothing decays, no forecast expires, no opportunity
# arrives later, and the answer to "trade now or wait" is the same at every stage by construction.
#
# `plan_receding` solves the actual decision. Stages have real lengths (an hour, three more, the
# rest of the day, the rest of the week), and each stage's scenarios are the desk's worlds with
# three things changed:
#
#   * EDGE DECAY  -- each sleeve's posterior edge (the world's own mu draw) is scaled by
#                    2^(-t/half_life) at the stage midpoint, so a perishable edge is worth less
#                    later and the plan front-loads it; a durable one is not rushed.
#   * FORECASTS   -- term-structured beliefs (`forward_path`) enter as a per-stage excess mean.
#                    OVERLAPPING HORIZONS ARE NOT INDEPENDENT PROFIT: a 1h forecast of +0.2R and a
#                    4h forecast of +0.5R are one path, +0.2R in the first hour and +0.3R over the
#                    next three, never +0.7R. They are converted to forward rates before use.
#   * OPPORTUNITY -- `available_from` holds a sleeve at zero until the stage it becomes tradable,
#                    so the plan can keep budget (and margin, via a per-stage `cap`) for it instead
#                    of filling the book now and paying to unwind it.
#
# The objective is the robust log growth of the path minus per-sleeve transaction cost on every
# change of heat between stages, starting from the HELD book:
#
#     max_{h_1..h_S}  sum_s L_s * G_s(h_s)  -  sum_s sum_i k_i |h_s,i - h_{s-1,i}|
#
# with G_s the same (1 - lam) mean + lam CVaR of per-world log growth `robust_elog` uses. It is
# concave (the L1 is smoothed by sqrt(x^2 + eps^2) - eps, convex and within eps of |x|), so
# projected ascent converges and the Frank-Wolfe gap is a certificate, published as such. Only
# h_1 is acted on; the rest is the plan that made h_1 cheap, re-solved on the next pass. TRADE
# NOW, PARTIALLY, WAIT, HOLD and CLOSE are not rules here -- they are read off the solved path per
# sleeve (`actions`), and the value of the whole plan against HOLDING the current book on the
# same scenarios and horizon, net of the same costs, is reported (`vs_hold`). The cost is charged
# ONCE, inside the objective; nothing downstream may charge it again.
# =================================================================================================

#: Stage lengths in days: one hour, the next three, the rest of the day, the rest of the week.
#: They sum to five days, the horizon `pf_allocator.NO_TRADE_HORIZON_DAYS` claims, so the planner
#: and the no-trade filter look exactly as far ahead as each other and can be compared.
DEFAULT_STAGE_DAYS: tuple[float, ...] = (1.0 / 24.0, 3.0 / 24.0, 20.0 / 24.0, 4.0)
#: Smoothing of |x| in the turnover charge. 1e-6 of heat is far below a lot step on any account.
L1_SMOOTH_EPS = 1e-6


def forward_path(forecasts: Sequence[tuple[float, Mapping[str, float]]],
                 stage_days: Sequence[float], names: Sequence[str]) -> np.ndarray:
    """Horizon-consistent per-stage excess mean, R per day, shape (S, N).

    `forecasts` is a list of (horizon_days, {sleeve: CUMULATIVE expected excess R over that
    horizon from now}). Cumulative forecasts at nested horizons are differenced into forward
    rates -- the 4h forecast contributes only what it says beyond the 1h one -- and each stage
    receives the time-weighted average forward rate over its own interval. Past the longest
    horizon the forecast says nothing and contributes zero, never an extrapolation. Two beliefs
    about the same horizon are one claim and are averaged, not added.
    """
    n, s_n = len(names), len(stage_days)
    out = np.zeros((s_n, n))
    edges = np.concatenate([[0.0], np.cumsum(np.asarray(stage_days, dtype=float))])
    for j, name in enumerate(names):
        merged: dict[float, list[float]] = {}
        for hz, f in forecasts:
            if name not in f:
                continue
            v = float(f[name])
            if float(hz) > 0.0 and np.isfinite(v):
                merged.setdefault(float(hz), []).append(v)
        if not merged:
            continue
        knots = [(0.0, 0.0)] + [(hz, float(np.mean(v))) for hz, v in sorted(merged.items())]
        for s in range(s_n):
            a, b = edges[s], edges[s + 1]
            acc = 0.0
            for (h0, c0), (h1, c1) in pairwise(knots):
                lo, hi = max(a, h0), min(b, h1)
                if hi > lo:
                    acc += (c1 - c0) / (h1 - h0) * (hi - lo)
            out[s, j] = acc / (b - a) if b > a else 0.0
    return out


def _robust_stage(r: np.ndarray, h: np.ndarray, lam: float, alpha: float
                  ) -> tuple[float, np.ndarray]:
    """(1 - lam) mean + lam CVaR_alpha of per-world mean log growth, and its supergradient."""
    port = np.einsum("wtn,n->wt", r, h.astype(np.float32), optimize=True).astype(np.float64)
    one_plus = 1.0 + port
    if not np.all(one_plus > 1e-9):
        return -np.inf, np.zeros_like(h)
    g_w = np.log(one_plus).mean(axis=1)
    n_w = g_w.size
    n_tail = max(1, round(alpha * n_w))
    tail = np.argpartition(g_w, n_tail - 1)[:n_tail]
    a = np.full(n_w, (1.0 - lam) / n_w)
    a[tail] += lam / n_tail
    u = (1.0 / one_plus) * a[:, None] / one_plus.shape[1]
    grad = np.einsum("wtn,wt->n", r, u.astype(np.float32), optimize=True).astype(np.float64)
    return float(a @ g_w), grad


def plan_receding(worlds: Worlds, h_prev: Mapping[str, float], *,
                  stage_days: Sequence[float] = DEFAULT_STAGE_DAYS,
                  cap: float | Sequence[float] = 0.30,
                  upper: Mapping[str, float] | None = None,
                  cost_one_way: float | Mapping[str, float] = 0.03,
                  half_life_days: Mapping[str, float] | None = None,
                  forecasts: Sequence[tuple[float, Mapping[str, float]]] = (),
                  available_from: Mapping[str, int] | None = None,
                  robust_lambda: float = 0.5, cvar_alpha: float = 0.2,
                  iterations: int = 300, step: float = 0.02,
                  action_tol: float = 1e-4) -> dict[str, Any]:
    """Receding-horizon E[log W] plan from the held book. See the block comment above.

    `cap` is total heat per stage (a sequence lets margin be preserved ahead of a known event);
    `cost_one_way` is account fraction per unit of heat moved, per sleeve or flat (the desk's
    0.06 round trip is 0.03 each way); `half_life_days` is each sleeve's edge half-life (absent
    means durable within the horizon); `available_from` is the first stage index a sleeve may be
    held in. Returns h_now, the path, per-sleeve actions, the value against holding, the
    optimality gap and the per-opportunity check of the five-day no-trade horizon.
    """
    from libs.portfolio.robust_elog import fw_vertex, project_capped_simplex

    names = list(worlds.names)
    n = len(names)
    lengths = np.asarray([float(x) for x in stage_days], dtype=float)
    s_n = int(lengths.size)
    if isinstance(cap, (int, float)):
        caps = np.full(s_n, float(cap))
    else:
        caps = np.asarray([float(c) for c in cap], dtype=float)
    if caps.size != s_n:
        raise ValueError(f"{caps.size} stage caps for {s_n} stages")
    if isinstance(cost_one_way, Mapping):
        kappa = np.array([float(cost_one_way.get(k, 0.03)) for k in names])
    else:
        kappa = np.full(n, float(cost_one_way))
    ub_base = (np.full(n, np.inf) if upper is None
               else np.array([float(upper.get(k, np.inf)) for k in names]))
    avail = available_from or {}
    ub = np.stack([np.where(np.array([int(avail.get(k, 0)) > s for k in names]), 0.0, ub_base)
                   for s in range(s_n)])                                     # (S, N)
    h0 = np.array([float(h_prev.get(k, 0.0)) for k in names])

    # Per-stage scenario tensors: decay the world's own edge draw, add the forward-rate forecast.
    mids = np.cumsum(lengths) - 0.5 * lengths
    hl = dict(half_life_days or {})
    mu = np.asarray(worlds.mu_draws, dtype=np.float64)                         # (W, N)
    fwd = (forward_path(forecasts, [float(x) for x in lengths], names) if forecasts
           else np.zeros((s_n, n)))
    stage_r: list[np.ndarray] = []
    for s in range(s_n):
        keep = np.array([2.0 ** (-mids[s] / float(hl[k])) if float(hl.get(k, 0.0) or 0.0) > 0
                         else 1.0 for k in names])
        shift = mu * (keep[None, :] - 1.0) + fwd[s][None, :]                   # (W, N)
        stage_r.append((worlds.r + shift[:, None, :].astype(np.float32)).astype(np.float32))

    def total(hs: np.ndarray) -> tuple[float, np.ndarray]:
        val, grad = 0.0, np.zeros_like(hs)
        for s in range(s_n):
            g, gr = _robust_stage(stage_r[s], hs[s], robust_lambda, cvar_alpha)
            if not np.isfinite(g):
                return -np.inf, grad
            val += lengths[s] * g
            grad[s] += lengths[s] * gr
        prev = np.vstack([h0[None, :], hs[:-1]])
        d = hs - prev
        sm = np.sqrt(d * d + L1_SMOOTH_EPS ** 2)
        val -= float((kappa[None, :] * (sm - L1_SMOOTH_EPS)).sum())
        dd = kappa[None, :] * d / sm
        grad -= dd
        grad[:-1] += dd[1:]
        return val, grad

    def project(hs: np.ndarray) -> np.ndarray:
        return np.stack([project_capped_simplex(hs[s], float(caps[s]), upper=ub[s])
                         for s in range(s_n)])

    hs = project(np.repeat(h0[None, :], s_n, axis=0))
    val, grad = total(hs)
    while not np.isfinite(val) and hs.sum() > 1e-12:
        hs = hs * 0.5
        val, grad = total(hs)
    lr, iters = step, 0
    for _ in range(iterations):
        iters += 1
        cand = project(hs + lr * grad)
        c_val, c_grad = total(cand)
        if c_val > val:
            moved = float(np.abs(cand - hs).sum())
            hs, val, grad = cand, c_val, c_grad
            lr *= 1.10
            if moved < 1e-9:
                break
        else:
            lr *= 0.5
            if lr < 1e-10:
                break
    if np.isfinite(val):
        gap = max(0.0, sum(float(grad[s] @ (fw_vertex(grad[s], float(caps[s]), upper=ub[s])
                                             - hs[s])) for s in range(s_n)))
        tol = max(1e-8, 1e-4 * abs(val))
    else:
        gap, tol = float("inf"), 0.0

    # HOLD on the same scenarios, horizon and costs: the held book, clipped only where a stage
    # makes it infeasible (a sleeve not yet tradable, a margin-reserving cap).
    hold = project(np.repeat(h0[None, :], s_n, axis=0))
    hold_val, _ = total(hold)

    actions: dict[str, dict[str, Any]] = {}
    g0 = grad[0] / max(float(lengths[0]), 1e-12)   # marginal log growth per day, stage one
    for j, k in enumerate(names):
        d_now, d_end = hs[0, j] - h0[j], hs[-1, j] - h0[j]
        if abs(d_end) < action_tol and abs(d_now) < action_tol:
            act = "HOLD"
        elif hs[0, j] < action_tol <= h0[j]:
            act = "CLOSE"
        elif abs(d_now) < action_tol:
            act = "WAIT"
        elif abs(d_end) < action_tol or np.sign(d_now) != np.sign(d_end):
            # Act now and unwind inside the horizon: a short-lived opportunity taken whole.
            act = "ADD_NOW_TRANSIENT" if d_now > 0 else "REDUCE_NOW_TRANSIENT"
        elif abs(d_now) >= 0.9 * abs(d_end):
            act = "ADD_NOW" if d_now > 0 else "REDUCE_NOW"
        else:
            act = "ADD_PARTIAL" if d_now > 0 else "REDUCE_PARTIAL"
        if act == "HOLD" and h0[j] < action_tol:
            continue
        # PER-OPPORTUNITY CHECK OF THE FIVE-DAY NO-TRADE HORIZON. The filter in pf_allocator
        # trades when gain/day x 5 exceeds the round-trip cost, which is right only when the
        # opportunity lasts five days. Break-even days are what this move needs; persistence is
        # how long the edge behind it keeps half its value (its half-life, or the forecast's own
        # horizon when the move is forecast-driven).
        move = d_end if abs(d_end) >= action_tol else d_now
        gain_day = abs(float(g0[j]) * move)
        cost = 2.0 * float(kappa[j]) * abs(move)
        persist = float(hl.get(k, 0.0) or 0.0) or float("inf")
        f_h = [float(hz) for hz, f in forecasts if k in f]
        if f_h and abs(float(fwd[:, j].sum())) > 0:
            persist = min(persist, max(f_h))
        be = cost / gain_day if gain_day > 0 else float("inf")
        actions[k] = {
            "action": act, "held": round(float(h0[j]), 6), "now": round(float(hs[0, j]), 6),
            "end": round(float(hs[-1, j]), 6),
            "breakeven_days": None if not np.isfinite(be) else round(float(be), 4),
            "persistence_days": None if not np.isfinite(persist) else round(persist, 4),
            "five_day_rule_trades": bool(gain_day * 5.0 > cost),
            "opportunity_pays": bool(be <= min(persist, float(lengths.sum()))),
        }
    disagree = sorted(k for k, a in actions.items()
                      if a["five_day_rule_trades"] != a["opportunity_pays"])
    return {
        "h_now": {k: round(float(v), 6) for k, v in zip(names, hs[0], strict=True)},
        "path_total_heat": [round(float(h.sum()), 6) for h in hs],
        "stage_days": [round(float(x), 6) for x in lengths],
        "objective": round(float(val), 10) if np.isfinite(val) else None,
        "vs_hold": {
            "hold_objective": round(float(hold_val), 10) if np.isfinite(hold_val) else None,
            "benefit": (round(float(val - hold_val), 10)
                        if np.isfinite(val) and np.isfinite(hold_val) else None),
            "basis": "same scenarios, stages and per-sleeve costs; hold = held book kept",
        },
        "optimality_gap": round(float(gap), 12), "gap_tolerance": tol,
        "converged": bool(np.isfinite(gap) and gap <= tol), "iterations": iters,
        "actions": actions,
        "no_trade_horizon_check": {
            "rule_days": 5.0, "disagree": disagree,
            "why": ("five_day_rule_trades is the pf_allocator filter's verdict on the same move; "
                    "opportunity_pays uses the edge's own persistence capped at the plan horizon. "
                    "A sleeve in `disagree` is one where a flat five days is the wrong horizon."),
        },
    }
