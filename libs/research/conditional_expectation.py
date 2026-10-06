"""CONDITIONAL EXPECTATION BY STATE, CAUSAL (Roman row 0997, 2026-10-06).

The law of total expectation, E[R] = sum_s P(S = s) E[R | S = s], and its variance partner,
Var(R) = E[Var(R | S)] + Var(E[R | S]), turned into a factory: any discrete state the desk can
compute before a bar (a vol tercile, a trend sign, a session, a weekday, a regime label) splits
the forward return into a between-state part (what the state explains) and a within-state part
(noise around it). A state is worth trading only where its conditional mean departs from the
total mean by more than its own standard error, and that is what `causal_state_means` reports
row by row.

CAUSAL. The forward return of row k covers (k, k + h], so it is admitted to the estimates only at
row k + h. Row t's estimates use exactly the outcomes completed by t; nothing later.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class StateMeans:
    mean: np.ndarray        # E[R | S = state[t]] from outcomes completed by t
    se: np.ndarray          # its standard error
    total: np.ndarray       # E[R] from the same outcomes
    count: np.ndarray       # outcomes behind `mean`


def causal_state_means(fwd: np.ndarray, state: np.ndarray, h: int, n_states: int,
                       min_n: int = 30) -> StateMeans:
    """Per-row conditional and total means of `fwd` (forward h-bar returns), admitting row k's
    outcome at row k + h. `state` holds integers in [0, n_states) or -1 for no state."""
    fwd = np.asarray(fwd, dtype=float)
    state = np.asarray(state, dtype=int)
    n = fwd.size
    s1, s2, cnt = np.zeros(n_states), np.zeros(n_states), np.zeros(n_states)
    t1 = t2 = tn = 0.0
    mean = np.full(n, np.nan)
    se = np.full(n, np.nan)
    total = np.full(n, np.nan)
    count = np.zeros(n, dtype=int)
    for t in range(n):
        k = t - h
        if k >= 0 and 0 <= state[k] < n_states and math.isfinite(fwd[k]):
            x = fwd[k]
            s = state[k]
            s1[s] += x
            s2[s] += x * x
            cnt[s] += 1
            t1 += x
            t2 += x * x
            tn += 1
        if tn >= min_n:
            total[t] = t1 / tn
        s = state[t]
        if 0 <= s < n_states and cnt[s] >= min_n:
            m = s1[s] / cnt[s]
            v = max(0.0, (s2[s] - cnt[s] * m * m) / (cnt[s] - 1))
            mean[t], se[t], count[t] = m, math.sqrt(v / cnt[s]), int(cnt[s])
    return StateMeans(mean, se, total, count)


def decomposition(fwd: np.ndarray, state: np.ndarray, n_states: int) -> dict[str, float]:
    """The in-sample law of total variance: the share of Var(R) that E[R | S] explains, with the
    per-state probabilities and means (a report, never a trading input)."""
    fwd = np.asarray(fwd, dtype=float)
    state = np.asarray(state, dtype=int)
    ok = np.isfinite(fwd) & (state >= 0) & (state < n_states)
    x, s = fwd[ok], state[ok]
    if x.size < 2:
        return {"n": int(x.size), "between_share": float("nan")}
    mu = float(x.mean())
    var = float(x.var())
    p = np.bincount(s, minlength=n_states) / x.size
    m = np.array([x[s == k].mean() if (s == k).any() else np.nan for k in range(n_states)])
    between = float(np.nansum(p * (m - mu) ** 2))
    total_from_states = float(np.nansum(p * m))
    return {"n": int(x.size), "total_mean": mu, "total_from_states": total_from_states,
            "between_share": between / var if var > 0 else float("nan"),
            "p": [round(float(v), 4) for v in p],
            "state_means": [None if not math.isfinite(v) else float(v) for v in m]}
