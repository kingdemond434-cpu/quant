"""THE ALLOCATOR'S PROOF SUITE: four challengers and one prospective baseline, all as shadows.

ALLOC-10/16/20/21 (backlog 2026-10-07). Each function answers one question the incumbent
E[log W] solver does not ask of itself, on the desk's own daily R matrix (T days x n sleeves,
R-multiples; book return = R @ heat):

  dro_book          ALLOC-20  What is the growth-optimal book when the mean of every sleeve may
                              be as bad as its one-sided 90% confidence bound AND its variance is
                              inflated by the same uncertainty? (a moment-ambiguity, distribution-
                              ally robust log-growth book -- not Kelly on a shrunk mean: the log is
                              taken scenario by scenario on the worst-case-shifted returns)
  disagreement_shrink  ALLOC-20  When HMM / GARCH / Bayesian / latent forecasts of a sleeve's mean
                              disagree, by how much should the mean be shrunk? (precision
                              weighting: model dispersion is added to the sampling variance)
  release_decision  ALLOC-21  Hold through an imminent release, trade now and go flat before it,
                              or wait? Priced in growth, from the sleeve's own release-day excess
                              variance.
  no_trade_band     ALLOC-16  Which rebalance band maximises realised net growth on the evidence,
                              instead of a constant turnover charge?
  attribution       ALLOC-10  How much of the allocator's realised growth over an equal-heat
                              baseline came from SELECTION, how much from SIZING, how much was
                              spent on COST?

None of this sizes anything. Every output is a report the incumbent is judged against.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

#: One-sided 90% normal quantile, the radius of the moment-ambiguity set: derived as
#: Phi^-1(0.90) = 1.2816, i.e. the true mean is below the ambiguity floor with probability 0.10.
DRO_Z = 1.2816
#: Floor on 1 + book return before the log: derived as the ruin boundary of a -100% day moved in
#: by 1e-9 so the log stays finite. It never binds at the heats this desk solves.
RUIN_EPS = 1e-9
#: Trading days per year, the calendar the desk annualises with (252 measured exchange days).
DAYS_PER_YEAR = 252.0


def _clean(r: np.ndarray) -> np.ndarray:
    out: np.ndarray = np.nan_to_num(np.asarray(r, dtype=float), nan=0.0)
    return out


def log_growth(r: np.ndarray, h: np.ndarray) -> float:
    port = _clean(r) @ np.asarray(h, dtype=float)
    return float(np.mean(np.log(np.maximum(1.0 + port, RUIN_EPS))))


def _project_simplex(v: np.ndarray, total: float) -> np.ndarray:
    """Euclidean projection onto {h >= 0, sum h = total}."""
    if total <= 0:
        return np.zeros_like(v)
    u = np.sort(v)[::-1]
    css = np.cumsum(u) - total
    ind = np.arange(1, v.size + 1)
    rho = int(np.nonzero(u - css / ind > 0)[0][-1])
    out: np.ndarray = np.maximum(v - css[rho] / (rho + 1.0), 0.0)
    return out


def max_log_book(r: np.ndarray, total: float, iters: int = 300) -> np.ndarray:
    """Long-only heat vector summing to `total` that maximises mean log growth on `r`."""
    r = _clean(r)
    n = r.shape[1]
    h = np.full(n, total / n)
    step = 1.0
    best = log_growth(r, h)
    for _ in range(iters):
        port = r @ h
        g = (r / np.maximum(1.0 + port, RUIN_EPS)[:, None]).mean(axis=0)
        while step > 1e-8:
            cand = _project_simplex(h + step * g, total)
            val = log_growth(r, cand)
            if val >= best:
                h, best = cand, val
                step *= 1.5
                break
            step *= 0.5
        else:
            break
    return h


def dro_book(r: np.ndarray, total: float, z: float = DRO_Z) -> dict[str, Any]:
    """Book that maximises log growth on worst-case-shifted, variance-inflated scenarios.

    Each sleeve's daily returns are shifted down by z standard errors of its mean (the worst mean
    inside the ambiguity set for a long-only book), and the de-meaned part is scaled by
    sqrt(1 + z^2 / T) so the scenario variance carries the estimation variance too.
    """
    r = _clean(r)
    t = r.shape[0]
    if t < 2 or r.shape[1] == 0:
        return {"status": "UNMEASURED", "why": "fewer than 2 days or no sleeves"}
    mu = r.mean(axis=0)
    se = r.std(axis=0, ddof=1) / math.sqrt(t)
    worst = (r - mu) * math.sqrt(1.0 + z * z / t) + (mu - z * se)
    h = max_log_book(worst, total)
    return {"status": "MEASURED", "heat": h, "worst_mean": mu - z * se, "z": z,
            "growth_worst_case": log_growth(worst, h), "growth_nominal": log_growth(r, h)}


def disagreement_shrink(means: Mapping[str, float], se: float) -> dict[str, Any]:
    """Combine model means for one sleeve; shrink toward 0 by the extra variance disagreement adds.

    Precision weighting: with sampling variance s^2 and between-model dispersion d^2, the
    posterior mean of a zero-centred prior with unit-information scale s^2 is
    mean * s^2 / (s^2 + d^2) relative to the agreement case -- so disagreement only ever
    shrinks, and full agreement (d = 0) shrinks nothing.
    """
    vals = np.array([float(v) for v in means.values() if v is not None and math.isfinite(v)])
    if vals.size < 2 or not (se > 0):
        return {"status": "UNMEASURED", "n_models": int(vals.size),
                "why": "fewer than 2 model means, or no standard error"}
    pooled = float(vals.mean())
    d2 = float(vals.var(ddof=1))
    factor = se * se / (se * se + d2)
    return {"status": "MEASURED", "n_models": int(vals.size), "pooled_mean": pooled,
            "dispersion": math.sqrt(d2), "shrink_factor": factor, "shrunk_mean": pooled * factor,
            "sign_agreement": bool(np.all(vals > 0) or np.all(vals < 0))}


def release_decision(mu_day: float, var_day: float, jump_var: float, hours_to_release: float,
                     cost: float = 0.0) -> dict[str, Any]:
    """Growth of three plans over the window up to and including an imminent release.

    With per-day mean mu and variance V (diffusive, accrued over the fraction f of a day before
    the release) and a zero-mean jump of variance J at the release, the growth-optimal value of a
    position held over a window with mean m and variance v, net of a round-trip cost c, is
    max(m - c, 0)^2 / (2 v):
        HOLD_THROUGH   m = f mu, v = f V + J
        FLAT_BEFORE    m = f mu, v = f V, paying the round trip (open now, close before)
        WAIT           0 (enter after the release, when the next window is priced afresh)
    """
    f = max(0.0, float(hours_to_release)) / 24.0
    if not (var_day > 0) or f <= 0:
        return {"status": "UNMEASURED", "why": "no variance or no time before the release"}
    m = f * mu_day
    jump = max(0.0, float(jump_var))

    def g(mean: float, var: float, c: float) -> float:
        return max(mean - c, 0.0) ** 2 / (2.0 * var) if var > 0 else 0.0

    plans = {"HOLD_THROUGH": g(m, f * var_day + jump, cost),
             "FLAT_BEFORE": g(m, f * var_day, 2.0 * cost),
             "WAIT": 0.0}
    # Ties go to the plan that trades least: WAIT, then HOLD_THROUGH (one entry), then
    # FLAT_BEFORE (a round trip) -- a plan that buys no growth is not worth an order.
    order = {"WAIT": 2, "HOLD_THROUGH": 1, "FLAT_BEFORE": 0}
    best = max(plans, key=lambda k: (plans[k], order[k]))
    return {"status": "MEASURED", "plans": plans, "best": best, "jump_var": jump,
            "fraction_of_day": f,
            "jump_to_diffusion": (jump / (f * var_day)) if f * var_day > 0 else None}


def release_jump_var(r: np.ndarray, is_release: np.ndarray) -> dict[str, Any]:
    """A sleeve's release-day excess variance: var(release days) - var(other days), floored at 0."""
    x = _clean(r).ravel()
    m = np.asarray(is_release, dtype=bool).ravel()
    if m.sum() < 3 or (~m).sum() < 10:
        return {"status": "UNMEASURED", "n_release_days": int(m.sum())}
    vr, vo = float(x[m].var(ddof=1)), float(x[~m].var(ddof=1))
    return {"status": "MEASURED", "n_release_days": int(m.sum()), "var_release": vr,
            "var_other": vo, "jump_var": max(0.0, vr - vo), "mu_other": float(x[~m].mean())}


def no_trade_band(r: np.ndarray, targets: np.ndarray, cost: float,
                  bands: Sequence[float]) -> dict[str, Any]:
    """Realised net growth of 'rebalance to the day's target only when L1 drift > band'.

    `targets` is (T x n): the book the allocator would have asked for each day (known at the day's
    open). Turnover is charged at `cost` per unit of heat traded. The calibrated band is the one
    with the highest realised net growth; ties go to the smaller band (react sooner).
    """
    r = _clean(r)
    tg = _clean(targets)
    if r.shape != tg.shape or r.shape[0] < 20:
        return {"status": "UNMEASURED", "why": "targets and returns differ in shape or < 20 days"}
    curve: dict[str, dict[str, float]] = {}
    for b in sorted(float(x) for x in bands):
        h = tg[0].copy()
        logs, traded, n_trades = 0.0, float(np.abs(h).sum()), 1
        logs -= cost * traded
        for t in range(r.shape[0]):
            if t > 0 and float(np.abs(tg[t] - h).sum()) > b:
                dh = float(np.abs(tg[t] - h).sum())
                traded += dh
                n_trades += 1
                logs -= cost * dh
                h = tg[t].copy()
            logs += math.log(max(1.0 + float(r[t] @ h), RUIN_EPS))
        curve[f"{b:g}"] = {"growth_per_day": logs / r.shape[0], "turnover": traded,
                           "n_rebalances": n_trades}
    best = max(curve, key=lambda k: (curve[k]["growth_per_day"], -float(k)))
    return {"status": "MEASURED", "best_band": float(best), "curve": curve, "cost": cost,
            "gain_vs_zero_band_per_day": (curve[best]["growth_per_day"]
                                          - curve[min(curve, key=float)]["growth_per_day"])}


def rolling_targets(r: np.ndarray, total: float, window: int = 60,
                    refit_every: int = 5) -> np.ndarray:
    """A causal target sequence for the band study: log-optimal on the trailing window, refit
    every `refit_every` days. Day t's target uses days < t only."""
    r = _clean(r)
    t_n, n = r.shape
    out = np.zeros((t_n, n))
    h = np.full(n, total / max(n, 1))
    for t in range(t_n):
        if t >= window and (t - window) % refit_every == 0:
            h = max_log_book(r[t - window:t], total, iters=60)
        out[t] = h
    return out


def attribution(r: np.ndarray, names: Sequence[str], allocator: Mapping[str, float],
                eligible: Sequence[str], cost_r: float = 0.0,
                prev: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Allocator vs an equal-heat baseline on the SAME realised days, split three ways.

        baseline   equal heat over every eligible sleeve, same total
        selected   equal heat over the sleeves the allocator funded, same total
        SELECTION = G(selected) - G(baseline);  SIZING = G(allocator) - G(selected)
        COST      = turnover charge of the allocator's move from `prev`, per day over the window
    """
    r = _clean(r)
    idx = {n: i for i, n in enumerate(names)}
    total = sum(float(v) for v in allocator.values() if v > 0)
    elig = [n for n in eligible if n in idx]
    funded = [n for n, v in allocator.items() if v > 0 and n in idx]
    if r.shape[0] < 1 or total <= 0 or not elig or not funded:
        return {"status": "UNMEASURED", "why": "no realised days, no funded or eligible sleeve"}

    def vec(book: Mapping[str, float]) -> np.ndarray:
        h = np.zeros(len(names))
        for k, v in book.items():
            if k in idx:
                h[idx[k]] = float(v)
        return h

    base = vec({n: total / len(elig) for n in elig})
    sel = vec({n: total / len(funded) for n in funded})
    alloc = vec(allocator)
    gb, gs, ga = log_growth(r, base), log_growth(r, sel), log_growth(r, alloc)
    turnover = (sum(abs(float(allocator.get(k, 0.0)) - float((prev or {}).get(k, 0.0)))
                    for k in set(allocator) | set(prev or {})) if prev is not None else 0.0)
    cost = cost_r * turnover / r.shape[0]
    return {"status": "MEASURED", "n_days": int(r.shape[0]), "growth_baseline": gb,
            "growth_selected_equal": gs, "growth_allocator": ga, "selection": gs - gb,
            "sizing": ga - gs, "cost": -cost, "net_vs_baseline": ga - gb - cost,
            "turnover": turnover}
