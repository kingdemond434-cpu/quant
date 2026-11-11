"""Control variates for tail simulations and portfolio stress (ROMAN-0970, ROMAN-0971).

Mandate audit 2026-10-06, "30 CONTROL VARIATES": apply control variates (variance reduction) to
tail simulations (0970) and portfolio stress (0971). Both rows were ABSENT.

WHY IT MATTERS FOR GROWTH. A tail number read off 2,000 bootstrap draws carries Monte Carlo noise.
That noise moves every consumer that reads it: a stress verdict, a drawdown budget, a survival
check. Noise in a tail estimate shows up as random swings in how much heat the book gets. A control
variate removes the part of that noise explained by a quantity whose expectation is KNOWN EXACTLY,
so the same draws buy a tighter estimate at no extra compute.

THE CONTROL. Under the circular stationary bootstrap (`stationary_indices`, the law of
`libs.validation.bootstrap.stationary_block_indices`) every resampled index is marginally uniform
over the sample, so the mean of a draw's book returns has expectation EXACTLY equal to the sample
mean of the book return. Nothing is assumed. That draw-mean is the control `X` with known `E[X] =
mu_x`, and it is strongly correlated with every path functional that matters: terminal log growth,
max drawdown, and whether the path breaches a loss level.

ESTIMATORS.
    mean      `cv_mean`: Y_cv = mean(Y) - beta (mean(X) - mu_x), beta = cov(Y, X) / var(X)
              estimated on the same draws (the usual O(1/n) bias, negligible at n in the
              thousands). It reports the variance reduction 1 - corr(Y, X)^2.
    tail      `cv_cvar`: the Rockafellar-Uryasev form CVaR_a = VaR + E[(L - VaR)+] / a, with VaR
              the sample quantile and the control applied to the excess E[(L - VaR)+], as in
              Glasserman (2004, sec. 9.2) and Hesterberg & Nelson (1998). The VaR itself is not
              control-adjusted.
    probability  `cv_mean` on the indicator 1{L >= level}. The result is clipped to [0, 1], and
              any clip is reported.

`stress` runs one synchronized-block simulation of a weighted book over a return matrix. It
reports each stress statistic plain and with its control variate, side by side, with the measured
variance reduction. The output is a report and moves no capital.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

#: Draws per stress run. DERIVATION: at 2000 draws a tail probability near 5% has a plain
#: standard error of sqrt(0.05*0.95/2000) = 0.49 percentage points before the control; the
#: control only tightens it. Matches `portfolio_monte_carlo`'s default of 2000.
DRAWS = 2000
#: Tail level for CVaR. 0.05 is the same worst-5% tail `portfolio_monte_carlo` reports.
ALPHA = 0.05
#: Minimum aligned rows. 60 is `portfolio_monte_carlo.MIN_COMMON_MARKS`.
MIN_ROWS = 60


def _beta(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    vx = float(np.var(x, ddof=1))
    if not vx > 0:
        return 0.0, 0.0
    c = float(np.cov(y, x, ddof=1)[0, 1])
    vy = float(np.var(y, ddof=1))
    rho2 = (c * c) / (vx * vy) if vy > 0 else 0.0
    return c / vx, min(max(rho2, 0.0), 1.0)


def cv_mean(y: Sequence[float] | np.ndarray, x: Sequence[float] | np.ndarray,
            mu_x: float) -> dict[str, Any]:
    """Control-variate estimate of E[Y], with its plain twin and both standard errors."""
    yy = np.asarray(y, dtype=float)
    xx = np.asarray(x, dtype=float)
    ok = np.isfinite(yy) & np.isfinite(xx)
    yy, xx = yy[ok], xx[ok]
    n = int(yy.size)
    if n < 3:
        return {"n": n, "status": "UNMEASURED", "why": f"{n} finite draws"}
    beta, rho2 = _beta(yy, xx)
    adj = yy - beta * (xx - float(mu_x))
    plain_se = float(np.std(yy, ddof=1)) / math.sqrt(n)
    cv_se = float(np.std(adj, ddof=1)) / math.sqrt(n)
    return {"n": n, "status": "MEASURED", "plain": float(yy.mean()), "cv": float(adj.mean()),
            "beta": beta, "plain_se": plain_se, "cv_se": cv_se,
            "variance_reduction": rho2,
            "efficiency": (plain_se / cv_se) ** 2 if cv_se > 0 else None}


def cv_cvar(losses: Sequence[float] | np.ndarray, x: Sequence[float] | np.ndarray, mu_x: float,
            alpha: float = ALPHA) -> dict[str, Any]:
    """CVaR at `alpha` of `losses` (positive = loss), plain and control-variate adjusted."""
    loss = np.asarray(losses, dtype=float)
    xx = np.asarray(x, dtype=float)
    ok = np.isfinite(loss) & np.isfinite(xx)
    loss, xx = loss[ok], xx[ok]
    if loss.size < max(3, math.ceil(2 / alpha)):
        return {"status": "UNMEASURED", "why": f"{loss.size} draws for alpha {alpha}"}
    var = float(np.quantile(loss, 1.0 - alpha))
    excess = np.maximum(loss - var, 0.0)
    m = cv_mean(excess, xx, mu_x)
    if m.get("status") != "MEASURED":
        return {"status": "UNMEASURED", "why": m.get("why")}
    return {"status": "MEASURED", "alpha": alpha, "var": var,
            "plain": var + float(m["plain"]) / alpha, "cv": var + max(float(m["cv"]), 0.0) / alpha,
            "plain_se": float(m["plain_se"]) / alpha, "cv_se": float(m["cv_se"]) / alpha,
            "variance_reduction": m["variance_reduction"], "efficiency": m["efficiency"]}


def _clip_prob(d: dict[str, Any]) -> dict[str, Any]:
    if d.get("status") == "MEASURED":
        raw = float(d["cv"])
        d["cv"] = min(max(raw, 0.0), 1.0)
        if d["cv"] != raw:
            d["clipped_from"] = raw
    return d


def stationary_indices(n: int, length: int, draws: int, mean_block: float,
                       rng: np.random.Generator) -> np.ndarray:
    """(draws, length) circular stationary-bootstrap indices into `n` rows, vectorised.

    The same law as `stationary_block_indices` (a new uniform start with probability 1/mean_block,
    else the next row mod n), so every index is marginally uniform on 0..n-1. That is what makes
    the control's expectation exact."""
    if mean_block < 1:
        raise ValueError("mean_block must be >= 1")
    new = rng.random((draws, length)) < 1.0 / mean_block
    new[:, 0] = True
    starts = rng.integers(0, n, size=(draws, length))
    pos = np.where(new, np.arange(length)[None, :], 0)
    first = np.maximum.accumulate(pos, axis=1)            # column where the current block began
    start_val = np.take_along_axis(starts, first, axis=1)
    return (start_val + (np.arange(length)[None, :] - first)) % n


def _max_dd_log(cum: np.ndarray) -> np.ndarray:
    peak = np.maximum.accumulate(np.concatenate([np.zeros((cum.shape[0], 1)), cum], axis=1),
                                 axis=1)[:, 1:]
    return np.max(peak - cum, axis=1)


def stress(returns: np.ndarray, weights: Sequence[float] | Mapping[str, float] | np.ndarray, *,
           names: Sequence[str] | None = None, horizon: int | None = None,
           draws: int = DRAWS, mean_block: float = 5.0, alpha: float = ALPHA,
           loss_levels: Sequence[float] = (0.05, 0.10), seed: int = 0) -> dict[str, Any]:
    """Synchronized-block stress of the book `weights . returns[t]`, plain vs control variate.

    `returns` is (T, k) per-unit-heat daily returns (NaN = flat). `weights` is a vector, or a
    mapping read through `names`. Each draw resamples `horizon` rows (default T) as one block of
    TIME for every column. Reports terminal log growth, max log drawdown, CVaR of the terminal log
    loss, and P(max drawdown >= level) for each `loss_levels` (log units)."""
    r = np.nan_to_num(np.asarray(returns, dtype=float), nan=0.0)
    if r.ndim != 2 or r.shape[0] < MIN_ROWS:
        return {"status": "UNMEASURED", "why": f"need a (T>={MIN_ROWS}, k) matrix"}
    if isinstance(weights, Mapping):
        if names is None:
            return {"status": "UNMEASURED", "why": "a weight mapping needs names"}
        w = np.array([float(weights.get(str(n), 0.0)) for n in names], dtype=float)
    else:
        w = np.asarray(weights, dtype=float)
    if w.size != r.shape[1]:
        return {"status": "UNMEASURED", "why": "weights do not match the matrix"}
    port = r @ w
    if np.any(port <= -1.0):
        return {"status": "UNMEASURED", "why": "a historical day ruins the book outright"}
    t = r.shape[0]
    h = int(horizon or t)
    idx = stationary_indices(t, h, int(draws), mean_block, np.random.default_rng(seed))
    sampled = port[idx]
    x = sampled.mean(axis=1)                      # the control, E[x] = mean(port) exactly
    mu_x = float(port.mean())
    cum = np.cumsum(np.log1p(sampled), axis=1)
    terminal = cum[:, -1]
    mdd = _max_dd_log(cum)
    out: dict[str, Any] = {
        "status": "MEASURED", "draws": int(draws), "rows": t, "horizon": h,
        "mean_block": mean_block, "control": "draw mean of book return; E = sample mean exactly",
        "control_mean": mu_x,
        "terminal_log_growth": cv_mean(terminal, x, mu_x),
        "max_drawdown_log": cv_mean(mdd, x, mu_x),
        "cvar_terminal_log_loss": cv_cvar(-terminal, x, mu_x, alpha),
        "p_drawdown": {f"{lv:g}": _clip_prob(cv_mean((mdd >= lv).astype(float), x, mu_x))
                       for lv in loss_levels},
    }
    return out


def headline(doc: Mapping[str, Any]) -> str:
    """One line: the variance each statistic lost to the control."""
    if doc.get("status") != "MEASURED":
        return f"control variates UNMEASURED: {doc.get('why')}"
    parts = []
    for k in ("terminal_log_growth", "max_drawdown_log", "cvar_terminal_log_loss"):
        v = doc.get(k) or {}
        if v.get("status") == "MEASURED":
            parts.append(f"{k} -{float(v['variance_reduction']):.0%} var")
    return "control variates: " + ", ".join(parts)
