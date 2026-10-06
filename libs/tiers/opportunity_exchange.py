"""THE OPPORTUNITY EXCHANGE AND NO-TRADE AS A FIRST-CLASS ACTION (Tier S layers 10, 24, 25).

Sleeves do not request risk. Every opportunity submits a BID:

    mu            posterior expected log-growth per period (after factory honesty)
    mu_sd         posterior uncertainty of mu
    sigma         return volatility per period
    friction      expected implementation cost per period (execution science)
    capacity      the largest fraction the opportunity can absorb
    decay_h       expected edge half-life in periods
    tail          expected shortfall at 5% (a positive number)
    current       the fraction held now
    mechanism     for the alternative-expression rule

The exchange CLEARS the book by maximising robust posterior E[log W]:

    max_w  sum_i w_i (mu_i - k mu_sd_i - friction_i) * decay_i  -  1/2 w' Sigma w
    s.t.   |w_i| <= capacity_i,  sum |w_i| sigma_i <= heat_ceiling

and prices every bid by its MARGINAL contribution dE[log W]/dw at the cleared book, so capital
flows to the highest posterior marginal growth, not the highest standalone Sharpe.

Every opportunity gets one of seven ACTIONS with its expected value:

    LONG / SHORT     open or grow toward the cleared weight
    REDUCE           cleared weight smaller than current, same sign
    EXIT             cleared weight zero from a nonzero holding
    ZERO             nothing held, nothing warranted: robust edge <= 0
    DEFER            point edge positive but the robust edge is not, and evidence is still
                     arriving -- waiting has option value, trading now does not
    ALT_EXPRESSION   another bid with the same mechanism clears more robust edge per unit of
                     friction: express the idea there instead

GROWTH GOVERNANCE. The resolved heat is filled, never reported short: if the cleared book's heat
is below the floor and positive robust edge exists, the book is scaled up to the floor (Rule 2),
never down below what the evidence supports (Rule 1). This organ runs in SHADOW: it publishes the
book it would clear beside the live allocator's, and the live allocator stays sovereign until the
principal says otherwise.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

F = npt.NDArray[np.float64]

ACTIONS = ("LONG", "SHORT", "REDUCE", "EXIT", "ZERO", "DEFER", "ALT_EXPRESSION")


@dataclass(frozen=True)
class Bid:
    key: str
    mu: float
    mu_sd: float
    sigma: float
    friction: float = 0.0
    capacity: float = 0.05
    decay_h: float | None = None
    tail: float | None = None
    current: float = 0.0
    mechanism: str = ""
    evidence_arriving: bool = True


def robust_edge(b: Bid, k: float, horizon: float) -> float:
    decay = 1.0
    if b.decay_h and b.decay_h > 0:
        decay = (1 - math.exp(-horizon * math.log(2) / b.decay_h)) / (
            horizon * math.log(2) / b.decay_h)
    return (b.mu - k * b.mu_sd - b.friction) * decay


def clear(bids: Sequence[Bid], corr: F | None = None, *, k: float = 1.0,
          heat_floor: float = 0.20, heat_ceiling: float = 0.30, horizon: float = 20.0,
          iters: int = 3000) -> dict[str, Any]:
    n = len(bids)
    if n == 0:
        return {"book": {}, "actions": {}, "heat": 0.0}
    mu_r = np.array([robust_edge(b, k, horizon) for b in bids])
    mu_p = np.array([b.mu - b.friction for b in bids])
    sig = np.array([max(b.sigma, 1e-9) for b in bids])
    cap = np.array([max(b.capacity, 0.0) for b in bids])
    c = np.eye(n) if corr is None else np.asarray(corr, dtype=float)
    cov = c * np.outer(sig, sig)
    # projected gradient ascent on the concave objective
    w = np.zeros(n)
    lr = 1.0 / (np.linalg.eigvalsh(cov).max() + 1e-12)
    for _ in range(iters):
        g = mu_r - cov @ w
        w = np.clip(w + lr * g, -cap, cap)
        heat = float(np.sum(np.abs(w) * sig))
        if heat > heat_ceiling:
            w *= heat_ceiling / heat
    heat = float(np.sum(np.abs(w) * sig))
    filled = False
    if 0 < heat < heat_floor and np.any(mu_r > 0):
        scale = heat_floor / heat
        w_up = np.clip(w * scale, -cap, cap)
        if float(np.sum(np.abs(w_up) * sig)) > heat:
            w, filled = w_up, True
        heat = float(np.sum(np.abs(w) * sig))
    marginal = mu_r - cov @ w
    elog = float(w @ mu_r - 0.5 * w @ cov @ w)
    book = {b.key: round(float(w[i]), 6) for i, b in enumerate(bids)}
    # actions
    best_by_mech: dict[str, tuple[float, str]] = {}
    for i, b in enumerate(bids):
        if not b.mechanism:
            continue
        score = mu_r[i] / (b.friction + 1e-9)
        if b.mechanism not in best_by_mech or score > best_by_mech[b.mechanism][0]:
            best_by_mech[b.mechanism] = (score, b.key)
    actions: dict[str, dict[str, Any]] = {}
    for i, b in enumerate(bids):
        wi, cur = float(w[i]), float(b.current)
        best = best_by_mech.get(b.mechanism)
        if abs(wi) < 1e-9:
            if mu_r[i] <= 0 < mu_p[i] and b.evidence_arriving:
                act = "DEFER"
            elif best and best[1] != b.key and mu_p[i] > 0:
                act = "ALT_EXPRESSION"
            elif abs(cur) > 1e-9:
                act = "EXIT"
            else:
                act = "ZERO"
        elif abs(cur) > 1e-9 and np.sign(cur) == np.sign(wi) and abs(wi) < abs(cur):
            act = "REDUCE"
        else:
            act = "LONG" if wi > 0 else "SHORT"
        actions[b.key] = {"action": act, "weight": round(wi, 6), "current": cur,
                          "robust_edge": round(float(mu_r[i]), 8),
                          "marginal_dElogW": round(float(marginal[i]), 8),
                          "alt": best[1] if act == "ALT_EXPRESSION" and best else None}
    counts: dict[str, int] = dict.fromkeys(ACTIONS, 0)
    for a in actions.values():
        counts[str(a["action"])] += 1
    return {"book": book, "actions": actions, "action_counts": counts,
            "heat": round(heat, 6), "heat_floor_filled": filled,
            "expected_log_growth": elog, "k": k,
            "rule": "shadow: publishes the cleared book; the live allocator stays sovereign"}


def compare(shadow: Mapping[str, float], live: Mapping[str, float], mu: Mapping[str, float]
            ) -> dict[str, Any]:
    keys = sorted(set(shadow) | set(live))
    diff = {k: round(float(shadow.get(k, 0.0)) - float(live.get(k, 0.0)), 6) for k in keys}
    g_s = sum(float(shadow.get(k, 0.0)) * float(mu.get(k, 0.0)) for k in keys)
    g_l = sum(float(live.get(k, 0.0)) * float(mu.get(k, 0.0)) for k in keys)
    return {"n": len(keys), "l1_distance": round(sum(abs(v) for v in diff.values()), 6),
            "linear_growth_shadow": g_s, "linear_growth_live": g_l,
            "largest_differences": dict(sorted(diff.items(), key=lambda kv: -abs(kv[1]))[:10])}
